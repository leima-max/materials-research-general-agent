"""Windows Word integration helpers for Zotero.

These tools do not synthesize Zotero field codes directly. They invoke Zotero's
official WinWord integration command path, which lets Zotero use its own
libzoteroWinWordIntegration.dll implementation to read/write Word fields.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastmcp import Context

from zotero_mcp._app import mcp
from zotero_mcp import client as _client
from zotero_mcp import utils as _utils

WordCommand = Literal[
    "addCitation",
    "editCitation",
    "addEditCitation",
    "addNote",
    "addBibliography",
    "editBibliography",
    "addEditBibliography",
    "citationExplorer",
    "refresh",
    "removeCodes",
    "setDocPrefs",
]

CitationMode = Literal["ask", "explicit", "auto", "hybrid"]

SUPPORTED_WORD_COMMANDS = {
    "addCitation",
    "editCitation",
    "addEditCitation",
    "addNote",
    "addBibliography",
    "editBibliography",
    "addEditBibliography",
    "citationExplorer",
    "refresh",
    "removeCodes",
    "setDocPrefs",
}

DEFAULT_TEMPLATE_VERSION = 1

_CITATION_NEAR_END_RE = re.compile(
    r"(\[[0-9,\-\s;]+\]|\([A-Z][^)]*?,\s*\d{4}[a-z]?\)|（[^）]*\d{4}[^）]*）)\s*$"
)
_SENTENCE_RE = re.compile(r"[^.!?。！？；;]+[.!?。！？；;]?")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{2,}")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

_STOPWORDS = {
    "about",
    "above",
    "after",
    "also",
    "and",
    "among",
    "are",
    "based",
    "because",
    "been",
    "between",
    "both",
    "can",
    "could",
    "during",
    "for",
    "from",
    "has",
    "have",
    "into",
    "more",
    "most",
    "not",
    "our",
    "such",
    "than",
    "that",
    "the",
    "their",
    "these",
    "this",
    "through",
    "was",
    "using",
    "were",
    "with",
    "within",
    "without",
}
_CLAIM_MARKERS = {
    "reported",
    "shown",
    "demonstrated",
    "suggest",
    "suggests",
    "indicate",
    "indicates",
    "enhanced",
    "improved",
    "reduced",
    "increased",
    "decreased",
    "attributed",
    "because",
    "therefore",
    "however",
    "whereas",
    "mechanism",
    "carrier",
    "trap",
    "band",
    "interface",
    "heterojunction",
    "perovskite",
    "photodetector",
    "mobility",
}
_DOMAIN_TERMS = {
    "pbs",
    "cspbbr3",
    "c60",
    "sno2",
    "ito",
    "fto",
    "ald",
    "eqe",
    "tem",
    "xrd",
    "hrtem",
    "fft",
}
_CN_TERMS = [
    "钙钛矿",
    "异质结",
    "陷阱态",
    "载流子",
    "外延",
    "界面",
    "响应度",
    "探测率",
    "迁移率",
    "光电探测",
]
_SEARCH_PHRASES = [
    "perovskite photodetector",
    "perovskite photodetectors",
    "trap states",
    "carrier dynamics",
    "carrier mobility",
    "charge separation",
    "band alignment",
    "built-in field",
    "heterojunction",
    "epitaxy",
]


def _default_zotero_candidates() -> list[Path]:
    candidates = []
    env_path = os.getenv("ZOTERO_EXECUTABLE")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "Zotero" / "zotero.exe",
            Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Zotero" / "zotero.exe",
        ]
    )

    which_path = shutil.which("zotero")
    if which_path:
        candidates.append(Path(which_path))

    return candidates


def _find_zotero_executable(explicit_path: str | None = None) -> Path | None:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        return path if path.exists() else None

    for path in _default_zotero_candidates():
        if path.exists():
            return path
    return None


def _build_word_integration_args(
    zotero_executable: Path,
    command: str,
    document: str | None,
    template_version: int,
) -> list[str]:
    args = [
        str(zotero_executable),
        "-ZoteroIntegrationAgent",
        "WinWord",
        "-ZoteroIntegrationCommand",
        command,
        "-ZoteroIntegrationTemplateVersion",
        str(template_version),
    ]
    if document:
        args.extend(["-ZoteroIntegrationDocument", document])
    return args


def _is_process_running(image_name: str) -> bool | None:
    if platform.system() != "Windows":
        return None
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    return image_name.lower() in completed.stdout.lower()


def _clean_word_paragraph_text(text: str) -> str:
    return text.replace("\r", "").replace("\x07", "").strip()


def _resolve_document_path(document_path: str) -> str:
    path = Path(document_path).expanduser()
    if not path.exists():
        raise RuntimeError(f"Document path does not exist: {document_path}")
    if not path.is_file():
        raise RuntimeError(f"Document path is not a file: {document_path}")
    return str(path.resolve())


def _get_word_application(allow_start: bool = True):
    if platform.system() != "Windows":
        raise RuntimeError("Microsoft Word automation is only supported on Windows.")
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as e:
        raise RuntimeError("pywin32 is required for Microsoft Word automation.") from e

    pythoncom.CoInitialize()
    try:
        return win32com.client.GetActiveObject("Word.Application")
    except Exception as e:
        if not allow_start:
            raise RuntimeError("Could not find a running Microsoft Word instance.") from e
    try:
        word_app = win32com.client.Dispatch("Word.Application")
        word_app.Visible = True
        return word_app
    except Exception as e:
        raise RuntimeError("Could not start Microsoft Word.") from e


def _get_active_word_selection():
    word_app = _get_word_application(allow_start=False)
    return word_app, word_app.Selection


def _read_active_word_paragraph() -> str:
    _word_app, selection = _get_active_word_selection()
    paragraph_range = selection.Range.Paragraphs(1).Range
    return _clean_word_paragraph_text(paragraph_range.Text)


def _get_active_word_document():
    word_app, _selection = _get_active_word_selection()
    try:
        return word_app, word_app.ActiveDocument
    except Exception as e:
        raise RuntimeError("Could not access the active Word document.") from e


def _get_or_open_word_document(document_path: str):
    resolved_path = _resolve_document_path(document_path)
    word_app = _get_word_application(allow_start=True)

    try:
        documents = word_app.Documents
        total = int(documents.Count)
    except Exception as e:
        raise RuntimeError("Could not access the Word documents collection.") from e

    target_key = resolved_path.casefold()
    for index in range(1, total + 1):
        try:
            document = documents(index)
            doc_path = _get_document_path(document)
        except Exception:
            continue
        if doc_path and str(Path(doc_path).resolve()).casefold() == target_key:
            try:
                document.Activate()
            except Exception:
                pass
            return word_app, document

    try:
        document = documents.Open(resolved_path)
        document.Activate()
        return word_app, document
    except Exception as e:
        raise RuntimeError(f"Could not open Word document: {resolved_path}") from e


def _get_word_document(document_path: str | None = None):
    if document_path:
        return _get_or_open_word_document(document_path)
    return _get_active_word_document()


def _get_word_selection(document_path: str | None = None):
    if document_path:
        word_app, _document = _get_or_open_word_document(document_path)
        return word_app, word_app.Selection
    return _get_active_word_selection()


def _read_word_paragraph(document_path: str | None = None) -> str:
    if not document_path:
        return _read_active_word_paragraph()
    _word_app, selection = _get_word_selection(document_path)
    paragraph_range = selection.Range.Paragraphs(1).Range
    return _clean_word_paragraph_text(paragraph_range.Text)


def _move_active_word_selection_to_offset(offset: int) -> int:
    _word_app, selection = _get_active_word_selection()
    paragraph_range = selection.Range.Paragraphs(1).Range
    start = int(paragraph_range.Start)
    end = max(start, int(paragraph_range.End) - 1)
    target = min(max(start + max(0, int(offset)), start), end)
    selection.SetRange(target, target)
    selection.Select()
    return target - start


def _move_word_selection_to_offset(offset: int, document_path: str | None = None) -> int:
    if not document_path:
        return _move_active_word_selection_to_offset(offset)
    _word_app, selection = _get_word_selection(document_path)
    paragraph_range = selection.Range.Paragraphs(1).Range
    start = int(paragraph_range.Start)
    end = max(start, int(paragraph_range.End) - 1)
    target = min(max(start + max(0, int(offset)), start), end)
    selection.SetRange(target, target)
    selection.Select()
    return target - start


def _count_zotero_fields(document) -> int:
    count = 0
    try:
        fields = document.Fields
        total = int(fields.Count)
    except Exception:
        return 0
    for index in range(1, total + 1):
        try:
            code = str(fields(index).Code.Text)
        except Exception:
            continue
        if "ZOTERO_ITEM CSL_CITATION" in code or "ZOTERO_BIBL" in code:
            count += 1
    return count


def _list_zotero_citation_ids(document) -> list[str]:
    ids: list[str] = []
    try:
        fields = document.Fields
        total = int(fields.Count)
    except Exception:
        return ids
    for index in range(1, total + 1):
        try:
            code = str(fields(index).Code.Text)
        except Exception:
            continue
        if "ZOTERO_ITEM CSL_CITATION" not in code:
            continue
        match = re.search(r'"citationID"\s*:\s*"([^"]+)"', code)
        if match:
            ids.append(match.group(1))
    return ids


def _verify_citation_ids(document, citation_ids: list[str]) -> tuple[list[str], list[str]]:
    found = set(_list_zotero_citation_ids(document))
    expected = [cid for cid in citation_ids if cid]
    present = [cid for cid in expected if cid in found]
    missing = [cid for cid in expected if cid not in found]
    return present, missing


def _get_document_path(document) -> str | None:
    try:
        path = str(document.FullName)
    except Exception:
        return None
    return path if path and path.lower() != "normal" else None


def _backup_active_document(document) -> str | None:
    doc_path = _get_document_path(document)
    if not doc_path:
        return None
    source = Path(doc_path)
    backup_dir = source.parent / "zotero_mcp_backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{source.stem}.zotero-mcp-backup-{stamp}{source.suffix}"
    document.SaveCopyAs(str(backup_path))
    return str(backup_path)


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in _SENTENCE_RE.finditer(text):
        raw_sentence = match.group(0)
        if not raw_sentence.strip():
            continue
        leading = len(raw_sentence) - len(raw_sentence.lstrip())
        trailing = len(raw_sentence.rstrip())
        start = match.start() + leading
        end = match.start() + trailing
        spans.append((start, end, text[start:end]))
    if not spans and text.strip():
        stripped = text.strip()
        start = text.index(stripped)
        spans.append((start, start + len(stripped), stripped))
    return spans


def _has_citation_near_end(sentence: str) -> bool:
    return bool(_CITATION_NEAR_END_RE.search(sentence.strip()))


def _extract_keywords(text: str, max_terms: int = 12) -> list[str]:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for idx, token in enumerate(_TOKEN_RE.findall(text)):
        token_norm = token.lower().strip("-+")
        if len(token_norm) < 3 or token_norm in _STOPWORDS:
            continue
        counts[token_norm] = counts.get(token_norm, 0) + 1
        first_seen.setdefault(token_norm, idx)

    for term in _DOMAIN_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE):
            counts[term] = counts.get(term, 0) + 3
            first_seen.setdefault(term, -1)

    for term in _CN_TERMS:
        if term in text:
            counts[term] = counts.get(term, 0) + 2
            first_seen.setdefault(term, len(first_seen))

    ranked = sorted(counts, key=lambda t: (-counts[t], first_seen[t], t))
    return ranked[:max_terms]


def _infer_insert_position(paragraph: str) -> dict[str, object]:
    text = _clean_word_paragraph_text(paragraph)
    if not text:
        return {
            "offset": 0,
            "sentence": "",
            "confidence": 0.0,
            "rationale": "Empty paragraph.",
        }

    best: tuple[float, int, int, str, list[str]] | None = None
    for start, end, sentence in _sentence_spans(text):
        lower_sentence = sentence.lower()
        reasons: list[str] = []
        score = 0.0

        markers = [term for term in _CLAIM_MARKERS if term in lower_sentence]
        if markers:
            score += min(len(markers), 4) * 1.4
            reasons.append("claim/domain terms: " + ", ".join(sorted(markers)[:4]))

        domain_terms = [term for term in _DOMAIN_TERMS if re.search(rf"\b{re.escape(term)}\b", sentence, re.I)]
        if domain_terms:
            score += min(len(domain_terms), 4) * 1.2
            reasons.append("materials/device terms: " + ", ".join(sorted(domain_terms)[:4]))

        if _YEAR_RE.search(sentence):
            score += 0.7
            reasons.append("contains year-like evidence")

        if re.search(r"\d", sentence):
            score += 0.5
            reasons.append("contains quantitative detail")

        if any(term in sentence for term in _CN_TERMS):
            score += 1.0
            reasons.append("contains Chinese domain terms")

        if _has_citation_near_end(sentence):
            score -= 3.0
            reasons.append("already appears to end with a citation")

        if len(sentence) > 180:
            score -= 0.4

        # Later citation-worthy sentences are often closer to where the user is writing.
        score += start / max(len(text), 1) * 0.3
        if best is None or score > best[0]:
            best = (score, start, end, sentence, reasons)

    if best is None:
        offset = len(text)
        return {
            "offset": offset,
            "sentence": text,
            "confidence": 0.2,
            "rationale": "No clear sentence boundary; inserting at paragraph end.",
        }

    score, _start, end, sentence, reasons = best
    confidence = max(0.1, min(0.95, (score + 2.0) / 8.0))
    rationale = "; ".join(reasons) if reasons else "Best available sentence by position."
    return {
        "offset": end,
        "sentence": sentence.strip(),
        "confidence": round(confidence, 2),
        "rationale": rationale,
    }


def _build_reference_queries(paragraph: str, sentence: str, max_queries: int = 8) -> list[str]:
    queries: list[str] = []
    lower_text = f"{sentence} {paragraph}".lower()
    domain_hits = [term for term in _DOMAIN_TERMS if re.search(rf"\b{re.escape(term)}\b", lower_text, re.I)]
    phrase_hits = [phrase for phrase in _SEARCH_PHRASES if phrase in lower_text]

    if domain_hits and phrase_hits:
        queries.append(" ".join(domain_hits[:2] + phrase_hits[:1]))
    if domain_hits:
        queries.append(" ".join(domain_hits[:3]))
    queries.extend(phrase_hits[:3])
    queries.extend(domain_hits[:4])

    sentence = sentence.strip()
    if sentence and len(sentence) <= 160:
        queries.append(sentence)

    sentence_keywords = _extract_keywords(sentence, max_terms=8)
    paragraph_keywords = _extract_keywords(paragraph, max_terms=10)
    for terms in (sentence_keywords, paragraph_keywords):
        if terms:
            queries.append(" ".join(terms[:8]))
            if len(terms) >= 4:
                queries.append(" ".join(terms[:4]))

    seen = set()
    deduped = []
    for query in queries:
        query = query.strip()
        if query and query.lower() not in seen:
            deduped.append(query)
            seen.add(query.lower())
    return deduped[:max_queries]


def _metadata_text(item: dict) -> str:
    data = item.get("data", {})
    tags = " ".join(t.get("tag", "") for t in data.get("tags", []) if isinstance(t, dict))
    creators = _utils.format_creators(data.get("creators", []))
    return " ".join(
        str(part)
        for part in [
            data.get("title", ""),
            data.get("abstractNote", ""),
            data.get("publicationTitle", ""),
            tags,
            creators,
        ]
        if part
    )


def _score_reference_candidate(item: dict, paragraph: str, sentence: str) -> tuple[float, list[str]]:
    data = item.get("data", {})
    title = data.get("title", "")
    metadata = _metadata_text(item)
    metadata_lower = metadata.lower()
    paragraph_tokens = set(_extract_keywords(paragraph, max_terms=18))
    sentence_tokens = set(_extract_keywords(sentence, max_terms=12))
    query_tokens = sentence_tokens or paragraph_tokens

    overlap = sorted(t for t in query_tokens if t.lower() in metadata_lower)
    title_overlap = sorted(t for t in query_tokens if t.lower() in title.lower())

    score = len(overlap) * 8.0 + len(title_overlap) * 6.0
    reasons: list[str] = []
    if title_overlap:
        reasons.append("title overlap: " + ", ".join(title_overlap[:5]))
    if overlap:
        reasons.append("metadata overlap: " + ", ".join(overlap[:6]))

    for term in _DOMAIN_TERMS:
        if term in paragraph.lower() and term in metadata_lower:
            score += 5.0
    if data.get("abstractNote"):
        score += 2.0
    if data.get("DOI"):
        score += 1.0

    item_type = data.get("itemType")
    if item_type in {"attachment", "note"}:
        score -= 100.0
    if not reasons:
        reasons.append("weak keyword match")
    return score, reasons


def _search_reference_candidates(paragraph: str, sentence: str, limit: int, ctx: Context) -> tuple[list[dict], list[str]]:
    queries = _build_reference_queries(paragraph, sentence)
    try:
        zot = _client.get_zotero_client()
    except Exception as e:
        ctx.warning(f"Zotero client is not available for reference matching: {e}")
        return [], queries

    by_key: dict[str, dict] = {}

    for query in queries:
        try:
            zot.add_parameters(q=query, limit=max(limit * 3, 10))
            for item in zot.items():
                key = item.get("key")
                if key and key not in by_key:
                    by_key[key] = item
        except Exception as e:
            ctx.warning(f"Zotero search failed for query '{query}': {e}")

    scored: list[tuple[float, list[str], dict]] = []
    for item in by_key.values():
        score, reasons = _score_reference_candidate(item, paragraph, sentence)
        if score > -50:
            scored.append((score, reasons, item))

    scored.sort(key=lambda entry: entry[0], reverse=True)
    candidates: list[dict] = []
    for score, reasons, item in scored[:limit]:
        copied = dict(item)
        copied["_match_score"] = round(score, 1)
        copied["_match_reasons"] = reasons
        candidates.append(copied)
    return candidates, queries


def _format_reference_suggestions(
    paragraph: str,
    position: dict[str, object],
    candidates: list[dict],
    queries: list[str],
) -> str:
    lines = [
        "# Word Paragraph Citation Suggestions",
        "",
        "## Insertion Point",
        f"- Offset: {position['offset']}",
        f"- Confidence: {position['confidence']}",
        f"- Insert after: {position['sentence']}",
        f"- Rationale: {position['rationale']}",
        "",
        "## Search Queries",
    ]
    lines.extend(f"- `{query}`" for query in queries)
    if not queries:
        lines.append("- No usable query terms found")

    lines.extend(["", "## Candidate References"])
    if not candidates:
        lines.append("No Zotero candidates found. Try selecting a more specific paragraph or adding a few manual keywords.")
        return "\n".join(lines)

    for index, item in enumerate(candidates, 1):
        extra = {
            "Match Score": str(item.get("_match_score", "")),
            "Why": "; ".join(item.get("_match_reasons", [])),
        }
        lines.extend(_utils.format_item_result(item, index=index, abstract_len=260, include_tags=True, extra_fields=extra))

    lines.extend(
        [
            "## Next Step",
            "Run `zotero_word_insert_citation_interactive` to move the Word cursor to the suggested insertion point and open Zotero's official citation dialog.",
        ]
    )
    return "\n".join(lines)


def _load_csl_item_data(zot, item_key: str, item: dict | None = None) -> dict:
    try:
        raw = zot.item(item_key, format="csljson")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return parsed[0]
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    if item is None:
        item = zot.item(item_key)
    data = item.get("data", {})
    csl_item: dict[str, object] = {
        "id": _item_uri(item),
        "type": "article-journal",
        "title": data.get("title", ""),
    }
    if data.get("date"):
        year = _YEAR_RE.search(str(data.get("date", "")))
        if year:
            csl_item["issued"] = {"date-parts": [[int(year.group(0))]]}
    authors = []
    for creator in data.get("creators", []):
        if not isinstance(creator, dict):
            continue
        author = {}
        if creator.get("lastName"):
            author["family"] = creator.get("lastName")
        if creator.get("firstName"):
            author["given"] = creator.get("firstName")
        if author:
            authors.append(author)
    if authors:
        csl_item["author"] = authors
    if data.get("DOI"):
        csl_item["DOI"] = data.get("DOI")
    if data.get("publicationTitle"):
        csl_item["container-title"] = data.get("publicationTitle")
    return csl_item


def _item_uri(item: dict) -> str:
    links = item.get("links", {})
    alternate = links.get("alternate", {}) if isinstance(links, dict) else {}
    href = alternate.get("href")
    if href:
        return str(href).replace("https://www.zotero.org", "http://zotero.org")

    library = item.get("library", {})
    library_id = library.get("id") if isinstance(library, dict) else os.getenv("ZOTERO_LIBRARY_ID", "0")
    return f"http://zotero.org/users/{library_id}/items/{item.get('key', '')}"


def _first_author_family(csl_item: dict) -> str:
    authors = csl_item.get("author") or []
    if isinstance(authors, list) and authors:
        first = authors[0]
        if isinstance(first, dict):
            return str(first.get("family") or first.get("literal") or "Citation")
    return "Citation"


def _issued_year(csl_item: dict) -> str:
    issued = csl_item.get("issued")
    if isinstance(issued, dict):
        date_parts = issued.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
            return str(date_parts[0][0])
    year = _YEAR_RE.search(json.dumps(csl_item, ensure_ascii=False))
    return year.group(0) if year else "n.d."


def _citation_display_text(csl_item: dict) -> str:
    author = _first_author_family(csl_item)
    authors = csl_item.get("author") or []
    suffix = " et al." if isinstance(authors, list) and len(authors) > 1 else ""
    return f"({author}{suffix}, {_issued_year(csl_item)})"


def _citation_cluster_display_text(csl_items: list[dict]) -> str:
    if not csl_items:
        return "(Citation)"
    inner = "; ".join(_citation_display_text(item).strip("()") for item in csl_items)
    return f"({inner})"


def _build_citation_payload(item: dict, csl_item: dict, citation_id: str | None = None) -> dict:
    return _build_citation_cluster_payload([(item, csl_item)], citation_id=citation_id)


def _build_citation_cluster_payload(
    item_pairs: list[tuple[dict, dict]],
    citation_id: str | None = None,
) -> dict:
    citation_id = citation_id or uuid.uuid4().hex[:10]
    citation_items = []
    csl_items = []
    for item, csl_item in item_pairs:
        uri = _item_uri(item)
        csl_id = str(csl_item.get("id") or uri)
        citation_items.append(
            {
                "id": csl_id,
                "uris": [uri],
                "itemData": csl_item,
            }
        )
        csl_items.append(csl_item)
    display_text = _citation_cluster_display_text(csl_items)
    return {
        "citationID": citation_id,
        "citationItems": citation_items,
        "properties": {
            "plainCitation": display_text,
            "formattedCitation": display_text,
        },
        "schema": "https://github.com/citation-style-language/schema/raw/master/csl-citation.json",
    }


def _build_zotero_word_field_code(payload: dict) -> str:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"ZOTERO_ITEM CSL_CITATION {compact}"


def _get_item_for_citation(item_key: str, ctx: Context) -> tuple[dict | None, dict | None, str | None]:
    try:
        zot = _client.get_zotero_client()
    except Exception as e:
        return None, None, f"Zotero client is not available: {e}"
    try:
        item = zot.item(item_key)
        csl_item = _load_csl_item_data(zot, item_key, item)
        return item, csl_item, None
    except Exception as e:
        ctx.error(f"Failed to load Zotero item {item_key}: {e}")
        return None, None, f"Failed to load Zotero item {item_key}: {e}"


def _get_items_for_citation(item_keys: list[str], ctx: Context) -> tuple[list[tuple[dict, dict]], str | None]:
    pairs: list[tuple[dict, dict]] = []
    for item_key in item_keys:
        item, csl_item, error = _get_item_for_citation(item_key, ctx)
        if error or item is None or csl_item is None:
            return [], error or f"Failed to load Zotero item {item_key}"
        pairs.append((item, csl_item))
    return pairs, None


def _insert_zotero_field_at_range(word_range, field_code: str, display_text: str):
    # 81 is wdFieldAddin. Word prefixes the code with ADDIN; Zotero expects
    # the add-in payload to start with ZOTERO_ITEM CSL_CITATION.
    field = word_range.Fields.Add(Range=word_range, Type=81, Text=field_code, PreserveFormatting=False)
    try:
        field.Result.Text = display_text
    except Exception:
        pass
    return field


def _insert_auto_citation_into_paragraph_range(paragraph_range, offset: int, payload: dict) -> tuple[str, str]:
    display_text = payload["properties"]["plainCitation"]
    field_code = _build_zotero_word_field_code(payload)
    start = int(paragraph_range.Start)
    end = max(start, int(paragraph_range.End) - 1)
    target = min(max(start + max(0, int(offset)), start), end)
    insertion_range = paragraph_range.Duplicate
    insertion_range.SetRange(target, target)
    _insert_zotero_field_at_range(insertion_range, field_code, display_text)
    return payload["citationID"], display_text


def _word_paragraph_records(document, max_paragraphs: int, min_chars: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        count = int(document.Paragraphs.Count)
    except Exception:
        return records
    count = min(count, max_paragraphs)
    for index in range(1, count + 1):
        try:
            paragraph = document.Paragraphs(index)
            paragraph_range = paragraph.Range
            text = _clean_word_paragraph_text(str(paragraph_range.Text))
            if len(text) < min_chars:
                continue
            if int(paragraph_range.Fields.Count) > 0:
                continue
            if _has_citation_near_end(text):
                continue
            records.append({"index": index, "text": text})
        except Exception:
            continue
    return records


def _normalize_item_keys(value: object) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[,;\s]+", value) if part.strip()]
        return parts
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _normalize_explicit_citation_plan(explicit_plan: list[dict] | str | None) -> tuple[list[dict[str, object]], str | None]:
    if explicit_plan in (None, "", []):
        return [], None
    raw_plan: object = explicit_plan
    if isinstance(explicit_plan, str):
        try:
            raw_plan = json.loads(explicit_plan)
        except json.JSONDecodeError as e:
            return [], f"explicit_plan must be JSON when provided as a string: {e}"
    if isinstance(raw_plan, dict):
        raw_plan = raw_plan.get("citations") or raw_plan.get("plan") or raw_plan.get("items")
    if not isinstance(raw_plan, list):
        return [], "explicit_plan must be a list of citation entries or an object containing `citations`."

    normalized: list[dict[str, object]] = []
    for index, entry in enumerate(raw_plan, 1):
        if not isinstance(entry, dict):
            return [], f"explicit_plan entry {index} must be an object."
        try:
            paragraph_index = int(entry.get("paragraph_index") or entry.get("paragraph") or entry.get("para"))
        except (TypeError, ValueError):
            return [], f"explicit_plan entry {index} must include an integer paragraph_index."
        if paragraph_index < 1:
            return [], f"explicit_plan entry {index} paragraph_index must be >= 1."

        item_keys = _normalize_item_keys(entry.get("item_keys") or entry.get("item_key") or entry.get("keys"))
        if not item_keys:
            return [], f"explicit_plan entry {index} must include item_keys or item_key."

        offset_spec = entry.get("offset", "auto")
        note = str(entry.get("note") or entry.get("reason") or "").strip()
        normalized.append(
            {
                "source": "explicit",
                "paragraph_index": paragraph_index,
                "offset_spec": offset_spec,
                "item_keys": item_keys,
                "note": note,
            }
        )
    return normalized, None


def _paragraph_text(document, paragraph_index: int) -> str:
    paragraph_range = document.Paragraphs(int(paragraph_index)).Range
    return _clean_word_paragraph_text(str(paragraph_range.Text))


def _resolve_citation_offset(document, paragraph_index: int, offset_spec: object) -> tuple[int, str]:
    text = _paragraph_text(document, paragraph_index)
    if offset_spec in (None, "", "auto", "after_sentence", "sentence_end"):
        position = _infer_insert_position(text)
        return int(position["offset"]), str(position["sentence"])
    if isinstance(offset_spec, str):
        normalized = offset_spec.strip().lower()
        if normalized in {"end", "paragraph_end"}:
            return len(text), text
        try:
            return max(0, int(normalized)), text
        except ValueError as e:
            raise RuntimeError(
                "offset must be an integer, `auto`, `after_sentence`, or `end`."
            ) from e
    try:
        return max(0, int(offset_spec)), text
    except (TypeError, ValueError) as e:
        raise RuntimeError("offset must be an integer, `auto`, `after_sentence`, or `end`.") from e


def _auto_plan_as_unified(plan: dict[str, object]) -> dict[str, object]:
    return {
        "source": "auto",
        "paragraph_index": int(plan["paragraph_index"]),
        "offset": int(plan["offset"]),
        "offset_spec": plan["offset"],
        "item_keys": [str(plan["item_key"])],
        "title": plan.get("title", "Untitled"),
        "score": plan.get("score", ""),
        "sentence": plan.get("sentence", ""),
        "queries": plan.get("queries", []),
    }


def _explicit_plan_as_unified(document, plan: dict[str, object]) -> dict[str, object]:
    offset, sentence = _resolve_citation_offset(document, int(plan["paragraph_index"]), plan.get("offset_spec", "auto"))
    unified = dict(plan)
    unified["offset"] = offset
    unified["sentence"] = sentence
    unified["score"] = "manual"
    unified["title"] = ", ".join(str(key) for key in plan["item_keys"])
    return unified


def _build_combined_citation_plans(
    document,
    mode: CitationMode,
    explicit_plan: list[dict[str, object]],
    max_insertions: int,
    min_chars: int,
    min_match_score: float,
    ctx: Context,
) -> tuple[list[dict[str, object]], str | None]:
    if mode == "ask":
        return [], None
    if mode == "explicit" and not explicit_plan:
        return [], "mode=explicit requires explicit_plan."
    if mode == "hybrid" and not explicit_plan:
        return [], "mode=hybrid requires explicit_plan; use mode=auto for automatic matching only."

    plans: list[dict[str, object]] = []
    explicit_paragraphs = {int(plan["paragraph_index"]) for plan in explicit_plan}
    if mode in {"explicit", "hybrid"}:
        for plan in explicit_plan:
            try:
                plans.append(_explicit_plan_as_unified(document, plan))
            except Exception as e:
                return [], f"Invalid explicit plan for paragraph {plan.get('paragraph_index')}: {e}"

    if mode in {"auto", "hybrid"}:
        remaining = max_insertions if mode == "auto" else max(0, max_insertions - len(plans))
        if remaining:
            auto_plans = _plan_document_citations(
                document,
                remaining,
                min_chars,
                min_match_score,
                ctx,
                exclude_paragraph_indices=explicit_paragraphs if mode == "hybrid" else None,
            )
            plans.extend(_auto_plan_as_unified(plan) for plan in auto_plans)
    return plans, None


def _format_combined_citation_plan(
    plans: list[dict[str, object]],
    mode: CitationMode,
    dry_run: bool,
    document_path: str | None,
    explicit_count: int,
) -> str:
    lines = [
        "# Zotero Word Citation Plan",
        "",
        f"- Mode: {mode}",
        f"- Execution: {'dry run' if dry_run else 'insert dynamic fields'}",
        f"- Document: {document_path or 'active Word document'}",
        f"- Explicit entries: {explicit_count}",
        f"- Planned insertions: {len(plans)}",
        "",
    ]
    if mode == "ask":
        lines.extend(
            [
                "No fields were inserted. Choose one of these modes and call the tool again:",
                "- `explicit`: use only the provided explicit_plan.",
                "- `auto`: ignore explicit_plan and use automatic Zotero matching.",
                "- `hybrid`: use explicit_plan for listed paragraphs, then automatic matching for unlisted paragraphs.",
            ]
        )
        return "\n".join(lines)
    if not plans:
        lines.append("No citation insertions are planned.")
        return "\n".join(lines)
    for index, plan in enumerate(plans, 1):
        lines.extend(
            [
                f"## {index}. Paragraph {plan['paragraph_index']} ({plan['source']})",
                f"- Item Keys: {', '.join(str(key) for key in plan['item_keys'])}",
                f"- Offset: {plan.get('offset')}",
                f"- Score: {plan.get('score', '')}",
                f"- Sentence: {plan.get('sentence', '')}",
            ]
        )
        if plan.get("note"):
            lines.append(f"- Note: {plan['note']}")
        if plan.get("title"):
            lines.append(f"- Title/Hint: {plan['title']}")
        lines.append("")
    return "\n".join(lines)


def _insert_unified_citation_plan(document, plans: list[dict[str, object]], ctx: Context) -> tuple[list[dict[str, object]], list[str]]:
    inserted: list[dict[str, object]] = []
    errors: list[str] = []
    resolved_plans = sorted(
        plans,
        key=lambda p: (int(p["paragraph_index"]), int(p.get("offset") or 0)),
        reverse=True,
    )
    for plan in resolved_plans:
        item_keys = [str(key) for key in plan.get("item_keys", [])]
        item_pairs, error = _get_items_for_citation(item_keys, ctx)
        if error:
            errors.append(f"Paragraph {plan['paragraph_index']}: {error}")
            continue
        payload = _build_citation_cluster_payload(item_pairs)
        try:
            paragraph_range = document.Paragraphs(int(plan["paragraph_index"])).Range
            citation_id, display_text = _insert_auto_citation_into_paragraph_range(
                paragraph_range,
                int(plan["offset"]),
                payload,
            )
            inserted.append(
                {
                    "source": plan["source"],
                    "paragraph_index": plan["paragraph_index"],
                    "item_keys": item_keys,
                    "citation_id": citation_id,
                    "display_text": display_text,
                }
            )
        except Exception as e:
            errors.append(f"Paragraph {plan['paragraph_index']}: {e}")
    return inserted, errors


def _plan_document_citations(
    document,
    max_insertions: int,
    min_chars: int,
    min_match_score: float,
    ctx: Context,
    exclude_paragraph_indices: set[int] | None = None,
) -> list[dict[str, object]]:
    plans: list[dict[str, object]] = []
    excluded = exclude_paragraph_indices or set()
    for record in _word_paragraph_records(document, max_paragraphs=500, min_chars=min_chars):
        if int(record["index"]) in excluded:
            continue
        paragraph = str(record["text"])
        position = _infer_insert_position(paragraph)
        candidates, queries = _search_reference_candidates(paragraph, str(position["sentence"]), 3, ctx)
        if not candidates:
            continue
        top = candidates[0]
        score = float(top.get("_match_score") or 0)
        if score < min_match_score:
            continue
        plans.append(
            {
                "paragraph_index": record["index"],
                "offset": position["offset"],
                "confidence": position["confidence"],
                "sentence": position["sentence"],
                "item_key": top.get("key"),
                "title": top.get("data", {}).get("title", "Untitled"),
                "score": score,
                "queries": queries,
            }
        )
        if len(plans) >= max_insertions:
            break
    return plans


def _format_batch_plan(plans: list[dict[str, object]], dry_run: bool, document_path: str | None = None) -> str:
    lines = [
        "# Zotero Word Batch Auto-Citation Plan",
        "",
        f"- Mode: {'dry run' if dry_run else 'execute'}",
        f"- Document: {document_path or 'active Word document'}",
        f"- Planned insertions: {len(plans)}",
        "",
    ]
    if not plans:
        lines.append("No eligible paragraphs found for automatic citation insertion.")
        return "\n".join(lines)
    for index, plan in enumerate(plans, 1):
        lines.extend(
            [
                f"## {index}. Paragraph {plan['paragraph_index']}",
                f"- Item Key: `{plan['item_key']}`",
                f"- Title: {plan['title']}",
                f"- Match Score: {plan['score']}",
                f"- Insertion Offset: {plan['offset']}",
                f"- Sentence: {plan['sentence']}",
                "",
            ]
        )
    return "\n".join(lines)


@mcp.tool(
    name="zotero_word_plugin_status",
    description="Check whether Zotero's Windows Word integration appears available on this machine.",
)
def word_plugin_status(
    zotero_executable: str | None = None,
    *,
    ctx: Context,
) -> str:
    """Report local prerequisites for invoking Zotero's Word integration."""

    system = platform.system()
    zotero_path = _find_zotero_executable(zotero_executable)
    integration_dir = zotero_path.parent / "integration" / "word-for-windows" if zotero_path else None
    template_path = integration_dir / "Zotero.dotm" if integration_dir else None
    dll_path = integration_dir / "libzoteroWinWordIntegration.dll" if integration_dir else None

    word_running = _is_process_running("WINWORD.EXE")
    zotero_running = _is_process_running("zotero.exe")

    lines = [
        "# Zotero Word Plugin Status",
        "",
        f"- Platform: {system}",
        f"- Windows supported: {'yes' if system == 'Windows' else 'no'}",
        f"- Zotero executable: {zotero_path if zotero_path else 'not found'}",
        f"- Word template: {template_path if template_path and template_path.exists() else 'not found'}",
        f"- WinWord integration DLL: {dll_path if dll_path and dll_path.exists() else 'not found'}",
        f"- Word process running: {_format_optional_bool(word_running)}",
        f"- Zotero process running: {_format_optional_bool(zotero_running)}",
        "",
        "Supported commands: " + ", ".join(sorted(SUPPORTED_WORD_COMMANDS)),
    ]
    ctx.info("Checked Zotero Word integration status")
    return "\n".join(lines)


def _format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


@mcp.tool(
    name="zotero_word_analyze_current_paragraph",
    description=(
        "Read the active Word paragraph or analyze provided text, infer a citation insertion point, "
        "and rank Zotero references that are likely relevant."
    ),
)
def word_analyze_current_paragraph(
    paragraph: str | None = None,
    limit: int | str = 5,
    document_path: str | None = None,
    *,
    ctx: Context,
) -> str:
    """Analyze a paragraph and suggest Zotero references for citation insertion."""

    try:
        limit_int = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        return "Error: limit must be an integer between 1 and 10."

    source = "provided text"
    if paragraph is None:
        try:
            paragraph = _read_word_paragraph(document_path)
            source = f"Word paragraph in {document_path}" if document_path else "active Word paragraph"
        except Exception as e:
            return f"Error reading active Word paragraph: {e}"

    paragraph = _clean_word_paragraph_text(paragraph)
    if not paragraph:
        return "Error: No paragraph text available for analysis."

    ctx.info(f"Analyzing {source} for Zotero citation suggestions")
    position = _infer_insert_position(paragraph)
    candidates, queries = _search_reference_candidates(paragraph, str(position["sentence"]), limit_int, ctx)

    response = _format_reference_suggestions(paragraph, position, candidates, queries)
    return response + f"\n\nSource: {source}"


@mcp.tool(
    name="zotero_word_insert_citation_interactive",
    description=(
        "Controlled MVP for automatic citation insertion: analyze the active Word paragraph, move the cursor "
        "to the suggested insertion point, and optionally open Zotero's official Add/Edit Citation dialog."
    ),
)
def word_insert_citation_interactive(
    limit: int | str = 5,
    dry_run: bool = True,
    document_path: str | None = None,
    zotero_executable: str | None = None,
    template_version: int = DEFAULT_TEMPLATE_VERSION,
    *,
    ctx: Context,
) -> str:
    """Move the Word cursor to a suggested citation point and open Zotero's citation dialog.

    dry_run defaults to True so callers can inspect candidates before touching Word.
    Set dry_run=False to move the active Word cursor and invoke Zotero Add/Edit Citation.
    """

    try:
        limit_int = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        return "Error: limit must be an integer between 1 and 10."

    try:
        paragraph = _read_word_paragraph(document_path)
    except Exception as e:
        return f"Error reading active Word paragraph: {e}"

    if not paragraph:
        return "Error: Active Word paragraph is empty."

    position = _infer_insert_position(paragraph)
    candidates, queries = _search_reference_candidates(paragraph, str(position["sentence"]), limit_int, ctx)
    suggestion = _format_reference_suggestions(paragraph, position, candidates, queries)

    if dry_run:
        return (
            suggestion
            + "\n\nDry run: Word cursor was not moved and Zotero dialog was not opened. "
            "Call this tool with `dry_run=false` after reviewing the candidate list."
        )

    try:
        actual_offset = _move_word_selection_to_offset(int(position["offset"]), document_path=document_path)
    except Exception as e:
        return f"Error moving Word cursor to suggested insertion point: {e}\n\n{suggestion}"

    command_result = word_plugin_command(
        command="addEditCitation",
        document_path=document_path,
        zotero_executable=zotero_executable,
        template_version=template_version,
        wait=False,
        ctx=ctx,
    )

    top = candidates[0] if candidates else None
    top_hint = ""
    if top:
        top_data = top.get("data", {})
        top_hint = (
            f"\n\nTop candidate to choose in the Zotero dialog: "
            f"`{top.get('key', '')}` — {top_data.get('title', 'Untitled')}"
        )

    return (
        f"Moved Word cursor to paragraph offset {actual_offset} and invoked Zotero Add/Edit Citation.\n\n"
        f"{command_result}{top_hint}\n\n{suggestion}"
    )


@mcp.tool(
    name="zotero_word_insert_citation_field_auto",
    description=(
        "Insert a Zotero-compatible ADDIN citation field into the active Word paragraph without opening "
        "the Zotero citation dialog. Defaults to dry_run for safety."
    ),
)
def word_insert_citation_field_auto(
    item_key: str | None = None,
    dry_run: bool = True,
    min_match_score: float | str = 25,
    backup: bool = True,
    refresh: bool = True,
    refresh_wait_seconds: int | str = 8,
    document_path: str | None = None,
    zotero_executable: str | None = None,
    *,
    ctx: Context,
) -> str:
    """Automatically insert one Zotero citation field into the active Word paragraph."""

    try:
        min_score = float(min_match_score)
        wait_seconds = max(0, int(refresh_wait_seconds))
    except (TypeError, ValueError):
        return "Error: min_match_score and refresh_wait_seconds must be numeric."

    try:
        word_app, selection = _get_word_selection(document_path)
        document = word_app.ActiveDocument
        paragraph_range = selection.Range.Paragraphs(1).Range
        paragraph = _clean_word_paragraph_text(str(paragraph_range.Text))
    except Exception as e:
        return f"Error reading active Word paragraph: {e}"

    if not paragraph:
        return "Error: Active Word paragraph is empty."

    position = _infer_insert_position(paragraph)
    candidates, queries = _search_reference_candidates(paragraph, str(position["sentence"]), 5, ctx)
    selected: dict | None = None
    if item_key:
        selected, csl_item, load_error = _get_item_for_citation(item_key, ctx)
        if load_error:
            return f"Error: {load_error}"
        selected_score = "manual"
    else:
        if not candidates:
            return _format_reference_suggestions(paragraph, position, candidates, queries)
        selected = candidates[0]
        selected_score = selected.get("_match_score", 0)
        if float(selected_score) < min_score:
            return (
                f"Top match score {selected_score} is below min_match_score {min_score}; no field inserted.\n\n"
                + _format_reference_suggestions(paragraph, position, candidates, queries)
            )
        item_key = str(selected.get("key"))
        selected, csl_item, load_error = _get_item_for_citation(item_key, ctx)
        if load_error:
            return f"Error: {load_error}"

    assert selected is not None and csl_item is not None and item_key is not None
    payload = _build_citation_payload(selected, csl_item)
    display_text = payload["properties"]["plainCitation"]
    field_code = _build_zotero_word_field_code(payload)
    title = selected.get("data", {}).get("title", "Untitled")

    plan_lines = [
        "# Zotero Word Automatic Citation Field",
        "",
        f"- Mode: {'dry run' if dry_run else 'execute'}",
        f"- Item Key: `{item_key}`",
        f"- Title: {title}",
        f"- Match Score: {selected_score}",
        f"- Document: {document_path or 'active Word document'}",
        f"- Citation ID: `{payload['citationID']}`",
        f"- Display Text: {display_text}",
        f"- Insertion Offset: {position['offset']}",
        f"- Insert after: {position['sentence']}",
    ]

    if dry_run:
        return "\n".join(plan_lines + ["", "Dry run: no Word field was inserted."])

    backup_path = None
    if backup:
        try:
            backup_path = _backup_active_document(document)
        except Exception as e:
            return f"Error creating Word document backup: {e}"

    before_count = _count_zotero_fields(document)
    try:
        citation_id, inserted_text = _insert_auto_citation_into_paragraph_range(
            paragraph_range,
            int(position["offset"]),
            payload,
        )
    except Exception as e:
        return f"Error inserting Zotero citation field into Word: {e}"
    after_count = _count_zotero_fields(document)

    refresh_result = "Refresh skipped."
    present: list[str] = []
    missing: list[str] = []
    if refresh:
        refresh_result = word_plugin_command(
            command="refresh",
            document_path=document_path,
            zotero_executable=zotero_executable,
            wait=False,
            ctx=ctx,
        )
        if wait_seconds:
            time.sleep(wait_seconds)
        present, missing = _verify_citation_ids(document, [citation_id])

    result_lines = plan_lines + [
        "",
        f"Requested citation display text: {inserted_text}",
        f"Zotero field count: {before_count} -> {after_count}",
        f"Backup: {backup_path or 'not created'}",
        f"Refresh: {refresh_result}",
        f"Verification: present={present or []}, missing={missing or []}",
    ]
    return "\n".join(result_lines)


@mcp.tool(
    name="zotero_word_refresh_and_verify",
    description="Invoke Zotero Word refresh and verify Zotero citation fields/citation IDs in the active document.",
)
def word_refresh_and_verify(
    citation_ids: list[str] | str | None = None,
    wait_seconds: int | str = 8,
    document_path: str | None = None,
    zotero_executable: str | None = None,
    *,
    ctx: Context,
) -> str:
    """Refresh Zotero fields in a Word document and verify inserted field IDs."""

    try:
        wait = max(0, int(wait_seconds))
    except (TypeError, ValueError):
        return "Error: wait_seconds must be an integer."

    if isinstance(citation_ids, str):
        try:
            parsed = json.loads(citation_ids)
            citation_ids = parsed if isinstance(parsed, list) else [citation_ids]
        except json.JSONDecodeError:
            citation_ids = [part.strip() for part in citation_ids.split(",") if part.strip()]
    citation_ids = citation_ids or []

    try:
        _word_app, document = _get_word_document(document_path)
    except Exception as e:
        return f"Error accessing active Word document: {e}"

    before_count = _count_zotero_fields(document)
    before_ids = _list_zotero_citation_ids(document)
    refresh_result = word_plugin_command(
        command="refresh",
        document_path=document_path,
        zotero_executable=zotero_executable,
        wait=False,
        ctx=ctx,
    )
    if wait:
        time.sleep(wait)
    after_count = _count_zotero_fields(document)
    after_ids = _list_zotero_citation_ids(document)
    present, missing = _verify_citation_ids(document, [str(cid) for cid in citation_ids])

    return "\n".join(
        [
            "# Zotero Word Refresh Verification",
            "",
            f"- Document: {document_path or 'active Word document'}",
            f"- Refresh command: {refresh_result}",
            f"- Zotero field count before: {before_count}",
            f"- Zotero field count after: {after_count}",
            f"- Citation IDs before: {before_ids}",
            f"- Citation IDs after: {after_ids}",
            f"- Expected IDs present: {present}",
            f"- Expected IDs missing: {missing}",
        ]
    )


@mcp.tool(
    name="zotero_word_insert_citations",
    description=(
        "Insert Zotero-compatible Word dynamic citation fields using explicit, automatic, or hybrid planning. "
        "For Word/.docx citation insertion, this dynamic-field route is the default; do not substitute "
        "plain-text bracketed numbers or a manually typed bibliography unless the user explicitly asks for static text. "
        "Defaults to mode=ask so the caller can choose the insertion strategy before fields are written."
    ),
)
def word_insert_citations(
    mode: CitationMode = "ask",
    explicit_plan: list[dict] | str | None = None,
    max_insertions: int | str = 10,
    min_chars: int | str = 80,
    min_match_score: float | str = 35,
    dry_run: bool = True,
    backup: bool = True,
    refresh: bool = True,
    refresh_wait_seconds: int | str = 10,
    save_after: bool = False,
    document_path: str | None = None,
    zotero_executable: str | None = None,
    *,
    ctx: Context,
) -> str:
    """Insert Zotero dynamic citation fields with explicit, automatic, or hybrid planning.

    Word/Docx citation tasks should produce `ADDIN ZOTERO_ITEM CSL_CITATION`
    fields by default. Static bracketed references are not a successful Zotero
    insertion unless the user explicitly requested static output.
    """

    if mode not in {"ask", "explicit", "auto", "hybrid"}:
        return "Error: mode must be one of `ask`, `explicit`, `auto`, or `hybrid`."

    try:
        max_items = max(1, min(int(max_insertions), 100))
        min_len = max(20, int(min_chars))
        min_score = float(min_match_score)
        wait_seconds = max(0, int(refresh_wait_seconds))
    except (TypeError, ValueError):
        return "Error: max_insertions, min_chars, min_match_score, and refresh_wait_seconds must be numeric."

    explicit_entries, plan_error = _normalize_explicit_citation_plan(explicit_plan)
    if plan_error:
        return f"Error: {plan_error}"

    if mode == "ask":
        return _format_combined_citation_plan(
            [],
            mode,
            dry_run=True,
            document_path=document_path,
            explicit_count=len(explicit_entries),
        )

    try:
        _word_app, document = _get_word_document(document_path)
    except Exception as e:
        return f"Error accessing Word document: {e}"

    plans, build_error = _build_combined_citation_plans(
        document,
        mode,
        explicit_entries,
        max_items,
        min_len,
        min_score,
        ctx,
    )
    if build_error:
        return f"Error: {build_error}"

    plan_text = _format_combined_citation_plan(
        plans,
        mode,
        dry_run=dry_run,
        document_path=document_path,
        explicit_count=len(explicit_entries),
    )
    if dry_run or not plans:
        return plan_text + "\n\nDry run: no Word fields were inserted."

    backup_path = None
    if backup:
        try:
            backup_path = _backup_active_document(document)
        except Exception as e:
            return f"Error creating Word document backup: {e}\n\n{plan_text}"

    before_count = _count_zotero_fields(document)
    inserted, errors = _insert_unified_citation_plan(document, plans, ctx)

    if save_after:
        try:
            document.Save()
        except Exception as e:
            errors.append(f"Save failed: {e}")

    after_count = _count_zotero_fields(document)
    refresh_result = "Refresh skipped."
    present: list[str] = []
    missing: list[str] = []
    if refresh and inserted:
        refresh_result = word_plugin_command(
            command="refresh",
            document_path=document_path,
            zotero_executable=zotero_executable,
            wait=False,
            ctx=ctx,
        )
        if wait_seconds:
            time.sleep(wait_seconds)
        present, missing = _verify_citation_ids(document, [str(row["citation_id"]) for row in inserted])

    result_lines = [
        plan_text,
        "",
        "# Execution Result",
        "",
        f"- Inserted fields: {len(inserted)}",
        f"- Zotero field count: {before_count} -> {after_count}",
        f"- Backup: {backup_path or 'not created'}",
        f"- Saved document: {'yes' if save_after else 'no'}",
        f"- Refresh: {refresh_result}",
        f"- Verification present: {present}",
        f"- Verification missing: {missing}",
    ]
    if inserted:
        result_lines.extend(["", "## Inserted"])
        for row in inserted:
            result_lines.append(
                f"- Paragraph {row['paragraph_index']} ({row['source']}): "
                f"`{', '.join(row['item_keys'])}` citationID=`{row['citation_id']}` "
                f"display={row['display_text']}"
            )
    if errors:
        result_lines.extend(["", "## Errors"])
        result_lines.extend(f"- {error}" for error in errors)
    return "\n".join(result_lines)


@mcp.tool(
    name="zotero_word_batch_auto_cite_document",
    description=(
        "Batch-process the active Word document: identify citation-worthy paragraphs, choose Zotero matches, "
        "insert Zotero-compatible dynamic citation fields, and refresh/verify. Defaults to dry_run. "
        "Use this instead of static-text citation insertion for Word/.docx documents."
    ),
)
def word_batch_auto_cite_document(
    max_insertions: int | str = 10,
    min_chars: int | str = 80,
    min_match_score: float | str = 35,
    dry_run: bool = True,
    backup: bool = True,
    refresh: bool = True,
    refresh_wait_seconds: int | str = 10,
    save_after: bool = False,
    document_path: str | None = None,
    zotero_executable: str | None = None,
    *,
    ctx: Context,
) -> str:
    """Automatically cite multiple paragraphs in a Word document."""

    try:
        max_items = max(1, min(int(max_insertions), 100))
        min_len = max(20, int(min_chars))
        min_score = float(min_match_score)
        wait_seconds = max(0, int(refresh_wait_seconds))
    except (TypeError, ValueError):
        return "Error: max_insertions, min_chars, min_match_score, and refresh_wait_seconds must be numeric."

    try:
        _word_app, document = _get_word_document(document_path)
    except Exception as e:
        return f"Error accessing active Word document: {e}"

    ctx.info(
        "Planning automatic Zotero citation insertions for "
        + (f"Word document {document_path}" if document_path else "active Word document")
    )
    plans = _plan_document_citations(document, max_items, min_len, min_score, ctx)
    plan_text = _format_batch_plan(plans, dry_run, document_path=document_path)
    if dry_run or not plans:
        return plan_text + "\n\nDry run: no Word fields were inserted."

    backup_path = None
    if backup:
        try:
            backup_path = _backup_active_document(document)
        except Exception as e:
            return f"Error creating Word document backup: {e}\n\n{plan_text}"

    before_count = _count_zotero_fields(document)
    inserted: list[dict[str, object]] = []
    errors: list[str] = []

    for plan in sorted(plans, key=lambda p: int(p["paragraph_index"]), reverse=True):
        item_key = str(plan["item_key"])
        item, csl_item, load_error = _get_item_for_citation(item_key, ctx)
        if load_error or item is None or csl_item is None:
            errors.append(f"Paragraph {plan['paragraph_index']}: {load_error}")
            continue
        payload = _build_citation_payload(item, csl_item)
        try:
            paragraph_range = document.Paragraphs(int(plan["paragraph_index"])).Range
            citation_id, display_text = _insert_auto_citation_into_paragraph_range(
                paragraph_range,
                int(plan["offset"]),
                payload,
            )
            inserted.append(
                {
                    "paragraph_index": plan["paragraph_index"],
                    "item_key": item_key,
                    "citation_id": citation_id,
                    "display_text": display_text,
                }
            )
        except Exception as e:
            errors.append(f"Paragraph {plan['paragraph_index']}: {e}")

    if save_after:
        try:
            document.Save()
        except Exception as e:
            errors.append(f"Save failed: {e}")

    after_count = _count_zotero_fields(document)
    refresh_result = "Refresh skipped."
    present: list[str] = []
    missing: list[str] = []
    if refresh and inserted:
        refresh_result = word_plugin_command(
            command="refresh",
            document_path=document_path,
            zotero_executable=zotero_executable,
            wait=False,
            ctx=ctx,
        )
        if wait_seconds:
            time.sleep(wait_seconds)
        present, missing = _verify_citation_ids(document, [str(row["citation_id"]) for row in inserted])

    result_lines = [
        plan_text,
        "",
        "# Execution Result",
        "",
        f"- Document: {document_path or 'active Word document'}",
        f"- Inserted fields: {len(inserted)}",
        f"- Zotero field count: {before_count} -> {after_count}",
        f"- Backup: {backup_path or 'not created'}",
        f"- Saved document: {'yes' if save_after else 'no'}",
        f"- Refresh: {refresh_result}",
        f"- Verification present: {present}",
        f"- Verification missing: {missing}",
    ]
    if inserted:
        result_lines.extend(["", "## Inserted"])
        for row in inserted:
            result_lines.append(
                f"- Paragraph {row['paragraph_index']}: `{row['item_key']}` "
                f"citationID=`{row['citation_id']}` display={row['display_text']}"
            )
    if errors:
        result_lines.extend(["", "## Errors"])
        result_lines.extend(f"- {error}" for error in errors)
    return "\n".join(result_lines)


@mcp.tool(
    name="zotero_word_plugin_command",
    description=(
        "Invoke an official Zotero Windows Word integration command such as "
        "addEditCitation, addBibliography, refresh, or setDocPrefs on the active Word document."
    ),
)
def word_plugin_command(
    command: WordCommand = "addEditCitation",
    document: str | None = None,
    document_path: str | None = None,
    zotero_executable: str | None = None,
    template_version: int = DEFAULT_TEMPLATE_VERSION,
    wait: bool = False,
    timeout: int = 15,
    *,
    ctx: Context,
) -> str:
    """Invoke Zotero's official WinWord integration command path.

    This opens Zotero's normal UI for commands such as addEditCitation. The tool
    intentionally does not accept item keys, because Zotero does not expose a
    supported headless WinWord command for inserting a specific citation cluster.
    """

    if platform.system() != "Windows":
        return "Error: Zotero Word plugin commands are only supported on Windows."

    if command not in SUPPORTED_WORD_COMMANDS:
        return (
            f"Error: Unsupported Word integration command '{command}'. "
            f"Supported commands: {', '.join(sorted(SUPPORTED_WORD_COMMANDS))}"
        )

    if document and document_path:
        return "Error: Pass either document or document_path, not both."

    target_document = document
    if document_path:
        try:
            target_document = _resolve_document_path(document_path)
        except Exception as e:
            return f"Error: {e}"

    zotero_path = _find_zotero_executable(zotero_executable)
    if not zotero_path:
        return (
            "Error: Zotero executable not found. Pass zotero_executable or set "
            "ZOTERO_EXECUTABLE to the full path of zotero.exe."
        )

    try:
        template_version = int(template_version)
    except (TypeError, ValueError):
        return "Error: template_version must be an integer."

    if template_version < DEFAULT_TEMPLATE_VERSION:
        return f"Error: template_version must be >= {DEFAULT_TEMPLATE_VERSION} for current Zotero WinWord integration."

    args = _build_word_integration_args(zotero_path, command, target_document, template_version)
    ctx.info(f"Invoking Zotero Word integration command: {command}")

    try:
        if wait:
            completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
            if completed.returncode != 0:
                details = (completed.stderr or completed.stdout or "").strip()
                return f"Error: Zotero command exited with code {completed.returncode}" + (
                    f"\n\n{details}" if details else ""
                )
        else:
            subprocess.Popen(args)
    except subprocess.TimeoutExpired:
        return f"Error: Zotero command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error invoking Zotero Word integration command: {e}"

    target = f"document '{target_document}'" if target_document else "the active Word document"
    if command in {"addCitation", "addEditCitation", "editCitation", "addNote"}:
        action = "Zotero should open its citation dialog or edit the citation at the cursor."
    elif command in {"addBibliography", "editBibliography", "addEditBibliography"}:
        action = "Zotero should add or edit the bibliography in Word."
    elif command == "refresh":
        action = "Zotero should refresh Zotero citation fields and bibliography."
    elif command == "setDocPrefs":
        action = "Zotero should open document preferences."
    elif command == "removeCodes":
        action = "Zotero should remove Zotero field codes from the document."
    else:
        action = "Zotero should run the requested Word integration command."

    return f"Started Zotero Word integration command `{command}` for {target}.\n\n{action}"
