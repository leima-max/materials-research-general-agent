---
name: zotero-literature-review
description: Use Zotero, Zotero MCP, local Zotero exports, and verified web sources to build citation-safe literature reviews, import bibliography lists into Zotero collections, audit metadata, attach legal/open-access PDFs, and prepare Word documents with Zotero dynamic citation fields.
---

# Zotero Literature Review Skill

Use this skill when the user asks for:

- Zotero-backed literature review or collection-based synthesis
- reference extraction from Word, PDF, RIS, BibTeX, CSV, or plain text
- Zotero collection creation, DOI import, duplicate cleanup, or metadata audit
- automatic PDF matching or attachment policy
- Word documents with Zotero dynamic citation fields

## Core Principles

1. Verify before writing. Do not invent titles, DOI values, journal names, page
   ranges, authors, or publication years.
2. Prefer DOI/Crossref/official metadata, then high-confidence title matching.
3. Use Zotero MCP when configured. Use exports or user-provided files when live
   Zotero access is unavailable.
4. For write operations, prefer MCP Web API or hybrid mode. Direct SQLite writes
   are a last resort and require backup, locked-state checks, and verification.
5. PDF automation must use legal open-access sources or user-authorized
   institutional access. Do not automate gray-market resolvers.

## Startup Checks

Run local Zotero readiness checks before claiming live Zotero coverage:

```bash
python scripts/run_smoke_test.py
python scripts/run_mcp_smoke_test.py
```

If the MCP namespace is unavailable or the smoke tests fail, ask for a Zotero
export file or permission to use web search.

## Workflow

### 1. Clarify Scope

Confirm:

- topic and keywords
- local Zotero only, web only, or combined search
- target collection name/key
- expected number of papers
- output format: Markdown, Word, RIS, BibTeX, CSV, or Zotero collection
- whether PDF auto-fetch is desired and what sources are authorized

### 2. Extract And Normalize References

Build a table with:

- source index
- raw reference
- title
- year
- first author
- DOI
- priority marker, if present
- matching confidence

### 3. Resolve Metadata

Use DOI first. If DOI is missing, search by exact title and accept only
high-confidence title/year matches. Flag ambiguous or supplementary-material
DOIs for manual review.

### 4. Import Or Update Zotero

Prefer MCP tools:

- `zotero_create_collection`
- `zotero_add_by_doi`
- `zotero_add_by_url`
- `zotero_add_from_file`
- `zotero_manage_collections`
- `zotero_update_item`

Use `attach_mode="auto"` when legal OA PDF attachment or linked-url fallback is
desired.

### 5. PDF Handling

Read `references/zotero-pdf-autofetch.md` before enabling PDF automation.
Expected behavior:

- MCP auto mode tries OA sources and links candidate PDF URLs if download fails.
- The Zotero plugin can observe newly added items and call Zotero's internal
  `Zotero.Attachments.addAvailableFiles()`.
- If neither path finds a PDF, report that no legal/open candidate was found.

### 6. Word Dynamic Citations

When asked to insert Zotero citations into `.docx`, prefer Zotero dynamic fields
over static bracketed references. Use MCP Word tools when available. If not
available, explain the fallback and verify resulting Word XML for
`ADDIN ZOTERO_ITEM CSL_CITATION` and `ADDIN ZOTERO_BIBL`.

### 7. Verification

Before reporting success, verify:

- collection exists and item count matches expectation
- each imported item has title, year, DOI when available, and creators
- items are in the expected collection
- requested tags were applied
- PDF/EPUB child attachments exist when expected
- no mojibake tags or private placeholders leaked into outputs

## Reference Workflows

- Batch bibliography import: `references/zotero-batch-import.md`
- PDF auto-fetch and plugin workflow: `references/zotero-pdf-autofetch.md`

## 中文摘要

当用户需要基于 Zotero 进行文献综述、参考文献导入、分类创建、PDF 自动匹配、元数据校验或 Word Zotero
动态引用域处理时使用本技能。核心原则是：先验证后写入，不编造文献信息，优先使用 DOI 和官方元数据，PDF
自动化只使用合法开放获取或用户已授权的机构来源。

