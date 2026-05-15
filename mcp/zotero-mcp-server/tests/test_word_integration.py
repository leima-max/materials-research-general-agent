"""Tests for Zotero Word integration command tools."""

import subprocess

import zotero_mcp.server as server
from zotero_mcp.tools import word


def test_word_plugin_command_invokes_zotero(monkeypatch, tmp_path, dummy_ctx):
    exe = tmp_path / "zotero.exe"
    exe.write_text("", encoding="utf-8")
    calls = []

    class FakePopen:
        def __init__(self, args):
            calls.append(args)

    monkeypatch.setattr(word.platform, "system", lambda: "Windows")
    monkeypatch.setattr(word.subprocess, "Popen", FakePopen)

    result = server.word_plugin_command(
        command="addEditCitation",
        zotero_executable=str(exe),
        ctx=dummy_ctx,
    )

    assert "Started Zotero Word integration command `addEditCitation`" in result
    assert calls == [
        [
            str(exe),
            "-ZoteroIntegrationAgent",
            "WinWord",
            "-ZoteroIntegrationCommand",
            "addEditCitation",
            "-ZoteroIntegrationTemplateVersion",
            "1",
        ]
    ]


def test_word_plugin_command_accepts_document_path(monkeypatch, tmp_path, dummy_ctx):
    exe = tmp_path / "zotero.exe"
    doc = tmp_path / "paper.docx"
    exe.write_text("", encoding="utf-8")
    doc.write_text("", encoding="utf-8")
    calls = []

    class FakePopen:
        def __init__(self, args):
            calls.append(args)

    monkeypatch.setattr(word.platform, "system", lambda: "Windows")
    monkeypatch.setattr(word.subprocess, "Popen", FakePopen)

    result = server.word_plugin_command(
        command="refresh",
        document_path=str(doc),
        zotero_executable=str(exe),
        ctx=dummy_ctx,
    )

    assert "Started Zotero Word integration command `refresh`" in result
    assert "-ZoteroIntegrationDocument" in calls[0]
    assert str(doc.resolve()) in calls[0]


def test_word_plugin_command_rejects_document_and_document_path(monkeypatch, tmp_path, dummy_ctx):
    exe = tmp_path / "zotero.exe"
    doc = tmp_path / "paper.docx"
    exe.write_text("", encoding="utf-8")
    doc.write_text("", encoding="utf-8")
    monkeypatch.setattr(word.platform, "system", lambda: "Windows")

    result = server.word_plugin_command(
        command="refresh",
        document="already-open.docx",
        document_path=str(doc),
        zotero_executable=str(exe),
        ctx=dummy_ctx,
    )

    assert "Pass either document or document_path" in result


def test_word_plugin_command_rejects_non_windows(monkeypatch, tmp_path, dummy_ctx):
    exe = tmp_path / "zotero.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(word.platform, "system", lambda: "Linux")

    result = server.word_plugin_command(
        command="addEditCitation",
        zotero_executable=str(exe),
        ctx=dummy_ctx,
    )

    assert result == "Error: Zotero Word plugin commands are only supported on Windows."


def test_word_plugin_command_rejects_unknown_command(monkeypatch, tmp_path, dummy_ctx):
    exe = tmp_path / "zotero.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(word.platform, "system", lambda: "Windows")

    result = server.word_plugin_command(
        command="insertSpecificItem",
        zotero_executable=str(exe),
        ctx=dummy_ctx,
    )

    assert "Unsupported Word integration command" in result


def test_word_plugin_command_wait_reports_nonzero(monkeypatch, tmp_path, dummy_ctx):
    exe = tmp_path / "zotero.exe"
    exe.write_text("", encoding="utf-8")

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(word.platform, "system", lambda: "Windows")
    monkeypatch.setattr(word.subprocess, "run", fake_run)

    result = server.word_plugin_command(
        command="refresh",
        zotero_executable=str(exe),
        wait=True,
        ctx=dummy_ctx,
    )

    assert "exited with code 1" in result
    assert "boom" in result


def test_word_plugin_status_reports_paths(monkeypatch, tmp_path, dummy_ctx):
    exe = tmp_path / "Zotero" / "zotero.exe"
    integration_dir = exe.parent / "integration" / "word-for-windows"
    integration_dir.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    (integration_dir / "Zotero.dotm").write_text("", encoding="utf-8")
    (integration_dir / "libzoteroWinWordIntegration.dll").write_text("", encoding="utf-8")

    monkeypatch.setattr(word.platform, "system", lambda: "Windows")
    monkeypatch.setattr(word, "_is_process_running", lambda _name: True)

    result = server.word_plugin_status(zotero_executable=str(exe), ctx=dummy_ctx)

    assert "Windows supported: yes" in result
    assert str(exe) in result
    assert "Word process running: yes" in result
    assert "addEditCitation" in result


class FakeSearchZotero:
    def __init__(self, items):
        self._items = items
        self.queries = []

    def add_parameters(self, **kwargs):
        self.queries.append(kwargs)

    def items(self):
        return self._items


def _sample_items():
    return [
        {
            "key": "PERO1234",
            "data": {
                "itemType": "journalArticle",
                "title": "Carrier transport and trap states in CsPbBr3 perovskite photodetectors",
                "date": "2023",
                "creators": [{"lastName": "Wang", "firstName": "A."}],
                "abstractNote": "CsPbBr3 devices show interface trap assisted carrier dynamics and improved response.",
                "tags": [{"tag": "CsPbBr3"}, {"tag": "photodetector"}],
                "DOI": "10.1234/example",
            },
        },
        {
            "key": "OTHER999",
            "data": {
                "itemType": "journalArticle",
                "title": "A study of unrelated organic synthesis",
                "date": "2020",
                "creators": [{"lastName": "Lee", "firstName": "B."}],
                "abstractNote": "Catalysis and synthesis.",
                "tags": [],
            },
        },
    ]


def test_infer_insert_position_prefers_citation_worthy_sentence():
    paragraph = (
        "The film is compact. Interface trap states in CsPbBr3 photodetectors can reduce carrier "
        "mobility and slow the response by 20 ms."
    )

    position = word._infer_insert_position(paragraph)

    assert "Interface trap states" in position["sentence"]
    assert position["offset"] == len(paragraph)
    assert position["confidence"] > 0.5


def test_word_analyze_current_paragraph_ranks_zotero_candidates(monkeypatch, dummy_ctx):
    fake_zot = FakeSearchZotero(_sample_items())
    monkeypatch.setattr(word._client, "get_zotero_client", lambda: fake_zot)

    result = server.word_analyze_current_paragraph(
        paragraph="CsPbBr3 perovskite photodetectors are limited by interface trap states and carrier mobility.",
        limit=2,
        ctx=dummy_ctx,
    )

    assert "PERO1234" in result
    assert "Carrier transport and trap states" in result
    assert "OTHER999" in result
    assert fake_zot.queries


def test_word_insert_citation_interactive_dry_run_does_not_move_or_open(monkeypatch, dummy_ctx):
    fake_zot = FakeSearchZotero(_sample_items())
    monkeypatch.setattr(word._client, "get_zotero_client", lambda: fake_zot)
    monkeypatch.setattr(
        word,
        "_read_active_word_paragraph",
        lambda: "CsPbBr3 photodetectors are affected by trap states and carrier dynamics.",
    )

    def fail_move(_offset):
        raise AssertionError("dry run should not move Word cursor")

    def fail_command(**_kwargs):
        raise AssertionError("dry run should not invoke Zotero command")

    monkeypatch.setattr(word, "_move_active_word_selection_to_offset", fail_move)
    monkeypatch.setattr(word, "word_plugin_command", fail_command)

    result = server.word_insert_citation_interactive(dry_run=True, ctx=dummy_ctx)

    assert "Dry run" in result
    assert "PERO1234" in result


def test_word_insert_citation_interactive_moves_and_invokes_plugin(monkeypatch, dummy_ctx):
    fake_zot = FakeSearchZotero(_sample_items())
    moved = []
    commands = []
    monkeypatch.setattr(word._client, "get_zotero_client", lambda: fake_zot)
    monkeypatch.setattr(
        word,
        "_read_active_word_paragraph",
        lambda: "CsPbBr3 photodetectors are affected by trap states and carrier dynamics.",
    )
    monkeypatch.setattr(word, "_move_active_word_selection_to_offset", lambda offset: moved.append(offset) or offset)

    def fake_command(**kwargs):
        commands.append(kwargs)
        return "Started Zotero Word integration command `addEditCitation`"

    monkeypatch.setattr(word, "word_plugin_command", fake_command)

    result = server.word_insert_citation_interactive(dry_run=False, ctx=dummy_ctx)

    assert moved
    assert commands[0]["command"] == "addEditCitation"
    assert "Moved Word cursor" in result
    assert "Top candidate" in result


class FakeCode:
    def __init__(self, text):
        self.Text = text


class FakeResult:
    def __init__(self):
        self.Text = ""


class FakeField:
    def __init__(self, code):
        self.Code = FakeCode(code)
        self.Result = FakeResult()


class FakeFields:
    def __init__(self):
        self.items = []

    @property
    def Count(self):
        return len(self.items)

    def __call__(self, index):
        return self.items[index - 1]

    def Add(self, Range=None, Type=None, Text="", PreserveFormatting=False):
        field = FakeField(f" ADDIN {Text}")
        self.items.append(field)
        return field


class FakeRange:
    def __init__(self, text, fields=None, start=0):
        self.Text = text
        self.Start = start
        self.End = start + len(text) + 1
        self.Fields = fields or FakeFields()
        self.last_range = None

    @property
    def Duplicate(self):
        return FakeRange("", self.Fields, self.Start)

    @property
    def Paragraphs(self):
        return FakeParagraphs([FakeParagraph(self)])

    def SetRange(self, start, end):
        self.last_range = (start, end)
        self.Start = start
        self.End = end


class FakeParagraph:
    def __init__(self, range_obj):
        self.Range = range_obj


class FakeParagraphs:
    def __init__(self, paragraphs):
        self.paragraphs = paragraphs

    @property
    def Count(self):
        return len(self.paragraphs)

    def __call__(self, index):
        return self.paragraphs[index - 1]


class FakeDocument:
    def __init__(self, texts):
        self.Fields = FakeFields()
        self.paragraphs = [FakeParagraph(FakeRange(text, self.Fields, start=i * 1000)) for i, text in enumerate(texts)]
        self.Paragraphs = FakeParagraphs(self.paragraphs)
        self.FullName = r"C:\tmp\paper.docx"
        self.saved = False
        self.backups = []

    def SaveCopyAs(self, path):
        self.backups.append(path)

    def Save(self):
        self.saved = True


class FakeWordApp:
    def __init__(self, document):
        self.ActiveDocument = document


class FakeSelection:
    def __init__(self, range_obj):
        self.Range = range_obj

    def SetRange(self, *_args):
        return None

    def Select(self):
        return None


def _sample_item_for_payload():
    item = {
        "key": "PERO1234",
        "library": {"id": 1234567, "type": "user"},
        "links": {"alternate": {"href": "https://www.zotero.org/users/1234567/items/PERO1234"}},
        "data": {"title": "Carrier transport in CsPbBr3", "itemType": "journalArticle"},
    }
    csl_item = {
        "id": "http://zotero.org/users/1234567/items/PERO1234",
        "type": "article-journal",
        "title": "Carrier transport in CsPbBr3",
        "author": [{"family": "Wang", "given": "A."}, {"family": "Li", "given": "B."}],
        "issued": {"date-parts": [[2023]]},
    }
    return item, csl_item


def test_build_zotero_word_field_code_contains_citation_payload():
    item, csl_item = _sample_item_for_payload()
    payload = word._build_citation_payload(item, csl_item, citation_id="abc123")
    code = word._build_zotero_word_field_code(payload)

    assert code.startswith("ZOTERO_ITEM CSL_CITATION ")
    assert '"citationID":"abc123"' in code
    assert "http://zotero.org/users/1234567/items/PERO1234" in code
    assert payload["properties"]["plainCitation"] == "(Wang et al., 2023)"


def test_word_insert_citation_field_auto_executes_without_dialog(monkeypatch, dummy_ctx):
    document = FakeDocument(["CsPbBr3 photodetectors are affected by interface trap states."])
    selection = FakeSelection(document.paragraphs[0].Range)
    item, csl_item = _sample_item_for_payload()

    monkeypatch.setattr(word, "_get_active_word_selection", lambda: (FakeWordApp(document), selection))
    monkeypatch.setattr(word, "_search_reference_candidates", lambda *_args, **_kwargs: ([], []))
    monkeypatch.setattr(word, "_get_item_for_citation", lambda *_args, **_kwargs: (item, csl_item, None))
    monkeypatch.setattr(word, "word_plugin_command", lambda **_kwargs: "refresh ok")

    result = server.word_insert_citation_field_auto(
        item_key="PERO1234",
        dry_run=False,
        refresh=True,
        refresh_wait_seconds=0,
        ctx=dummy_ctx,
    )

    assert "Requested citation display text" in result
    assert document.Fields.Count == 1
    assert "ZOTERO_ITEM CSL_CITATION" in document.Fields(1).Code.Text
    assert document.Fields(1).Result.Text == "(Wang et al., 2023)"


def test_word_refresh_and_verify_reports_expected_ids(monkeypatch, dummy_ctx):
    document = FakeDocument(["Paragraph"])
    document.Fields.items.append(FakeField(' ADDIN ZOTERO_ITEM CSL_CITATION {"citationID":"abc123"}'))
    monkeypatch.setattr(word, "_get_active_word_document", lambda: (FakeWordApp(document), document))
    monkeypatch.setattr(word, "word_plugin_command", lambda **_kwargs: "refresh ok")

    result = server.word_refresh_and_verify(citation_ids=["abc123"], wait_seconds=0, ctx=dummy_ctx)

    assert "Expected IDs present: ['abc123']" in result
    assert "Expected IDs missing: []" in result


def test_word_refresh_and_verify_uses_document_path(monkeypatch, dummy_ctx):
    document = FakeDocument(["Paragraph"])
    document.Fields.items.append(FakeField(' ADDIN ZOTERO_ITEM CSL_CITATION {"citationID":"abc123"}'))
    seen = {}

    def fake_get_word_document(document_path=None):
        seen["document_path"] = document_path
        return FakeWordApp(document), document

    def fake_command(**kwargs):
        seen["command_kwargs"] = kwargs
        return "refresh ok"

    monkeypatch.setattr(word, "_get_word_document", fake_get_word_document)
    monkeypatch.setattr(word, "word_plugin_command", fake_command)

    result = server.word_refresh_and_verify(
        citation_ids=["abc123"],
        document_path=r"C:\tmp\paper.docx",
        wait_seconds=0,
        ctx=dummy_ctx,
    )

    assert seen["document_path"] == r"C:\tmp\paper.docx"
    assert seen["command_kwargs"]["document_path"] == r"C:\tmp\paper.docx"
    assert "Document: C:\\tmp\\paper.docx" in result


def test_word_batch_auto_cite_document_executes_plans(monkeypatch, dummy_ctx):
    document = FakeDocument([
        "CsPbBr3 photodetectors are affected by interface trap states and carrier dynamics.",
        "PbS heterojunctions improve charge separation in perovskite devices.",
    ])
    item, csl_item = _sample_item_for_payload()
    plans = [
        {"paragraph_index": 1, "offset": 79, "confidence": 0.9, "sentence": "s1", "item_key": "PERO1234", "title": "T1", "score": 50, "queries": []},
        {"paragraph_index": 2, "offset": 64, "confidence": 0.9, "sentence": "s2", "item_key": "PERO1234", "title": "T1", "score": 49, "queries": []},
    ]

    monkeypatch.setattr(word, "_get_active_word_document", lambda: (FakeWordApp(document), document))
    monkeypatch.setattr(word, "_plan_document_citations", lambda *_args, **_kwargs: plans)
    monkeypatch.setattr(word, "_get_item_for_citation", lambda *_args, **_kwargs: (item, csl_item, None))
    monkeypatch.setattr(word, "word_plugin_command", lambda **_kwargs: "refresh ok")

    result = server.word_batch_auto_cite_document(
        dry_run=False,
        refresh=True,
        refresh_wait_seconds=0,
        save_after=True,
        ctx=dummy_ctx,
    )

    assert "Inserted fields: 2" in result
    assert document.Fields.Count == 2
    assert document.saved is True
    assert "Verification missing: []" in result


def test_word_batch_auto_cite_document_uses_document_path(monkeypatch, dummy_ctx):
    document = FakeDocument([
        "CsPbBr3 photodetectors are affected by interface trap states and carrier dynamics.",
    ])
    item, csl_item = _sample_item_for_payload()
    plans = [
        {
            "paragraph_index": 1,
            "offset": 79,
            "confidence": 0.9,
            "sentence": "s1",
            "item_key": "PERO1234",
            "title": "T1",
            "score": 50,
            "queries": [],
        },
    ]
    seen = {}

    def fake_get_word_document(document_path=None):
        seen["document_path"] = document_path
        return FakeWordApp(document), document

    def fake_command(**kwargs):
        seen["command_kwargs"] = kwargs
        return "refresh ok"

    monkeypatch.setattr(word, "_get_word_document", fake_get_word_document)
    monkeypatch.setattr(word, "_plan_document_citations", lambda *_args, **_kwargs: plans)
    monkeypatch.setattr(word, "_get_item_for_citation", lambda *_args, **_kwargs: (item, csl_item, None))
    monkeypatch.setattr(word, "word_plugin_command", fake_command)

    result = server.word_batch_auto_cite_document(
        dry_run=False,
        refresh=True,
        refresh_wait_seconds=0,
        save_after=True,
        document_path=r"C:\tmp\paper.docx",
        ctx=dummy_ctx,
    )

    assert seen["document_path"] == r"C:\tmp\paper.docx"
    assert seen["command_kwargs"]["document_path"] == r"C:\tmp\paper.docx"
    assert "Document: C:\\tmp\\paper.docx" in result
    assert document.Fields.Count == 1


def test_word_insert_citations_ask_mode_does_not_open_document(monkeypatch, dummy_ctx):
    def fail_get_document(*_args, **_kwargs):
        raise AssertionError("ask mode should not open Word")

    monkeypatch.setattr(word, "_get_word_document", fail_get_document)

    result = server.word_insert_citations(
        mode="ask",
        explicit_plan=[{"paragraph_index": 1, "item_keys": ["PERO1234"]}],
        document_path=r"C:\tmp\paper.docx",
        ctx=dummy_ctx,
    )

    assert "Choose one of these modes" in result
    assert "`explicit`" in result
    assert "`auto`" in result
    assert "`hybrid`" in result
    assert "Explicit entries: 1" in result


def test_word_insert_citations_explicit_executes_dynamic_field(monkeypatch, dummy_ctx):
    document = FakeDocument(["CsPbBr3 photodetectors are affected by interface trap states."])
    item, csl_item = _sample_item_for_payload()
    seen = {}

    monkeypatch.setattr(word, "_get_word_document", lambda document_path=None: (FakeWordApp(document), document))
    monkeypatch.setattr(word, "_get_item_for_citation", lambda *_args, **_kwargs: (item, csl_item, None))

    def fake_command(**kwargs):
        seen["command_kwargs"] = kwargs
        return "refresh ok"

    monkeypatch.setattr(word, "word_plugin_command", fake_command)

    result = server.word_insert_citations(
        mode="explicit",
        explicit_plan=[{"paragraph_index": 1, "offset": "end", "item_keys": ["PERO1234"], "note": "manual"}],
        dry_run=False,
        refresh=True,
        refresh_wait_seconds=0,
        document_path=r"C:\tmp\paper.docx",
        ctx=dummy_ctx,
    )

    assert "Inserted fields: 1" in result
    assert "Paragraph 1 (explicit)" in result
    assert document.Fields.Count == 1
    assert "ZOTERO_ITEM CSL_CITATION" in document.Fields(1).Code.Text
    assert seen["command_kwargs"]["document_path"] == r"C:\tmp\paper.docx"


def test_word_insert_citations_hybrid_uses_explicit_and_auto(monkeypatch, dummy_ctx):
    document = FakeDocument([
        "CsPbBr3 photodetectors are affected by interface trap states and carrier dynamics.",
        "PbS heterojunctions improve charge separation in perovskite devices and reduce recombination.",
    ])
    item, csl_item = _sample_item_for_payload()
    candidate = {
        "key": "PERO1234",
        "data": {"title": "Carrier transport in CsPbBr3"},
        "_match_score": 60,
    }

    monkeypatch.setattr(word, "_get_word_document", lambda document_path=None: (FakeWordApp(document), document))
    monkeypatch.setattr(word, "_get_item_for_citation", lambda *_args, **_kwargs: (item, csl_item, None))
    monkeypatch.setattr(word, "_search_reference_candidates", lambda *_args, **_kwargs: ([candidate], ["query"]))
    monkeypatch.setattr(word, "word_plugin_command", lambda **_kwargs: "refresh ok")

    result = server.word_insert_citations(
        mode="hybrid",
        explicit_plan='[{"paragraph_index": 1, "offset": "end", "item_keys": ["PERO1234"]}]',
        max_insertions=5,
        min_chars=20,
        min_match_score=10,
        dry_run=False,
        refresh=True,
        refresh_wait_seconds=0,
        ctx=dummy_ctx,
    )

    assert "Paragraph 1 (explicit)" in result
    assert "Paragraph 2 (auto)" in result
    assert "Inserted fields: 2" in result
    assert document.Fields.Count == 2
