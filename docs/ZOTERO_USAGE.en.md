# Zotero Skill Pack Usage

## 1. Install Zotero

Install Zotero Desktop and enable the local Connector endpoint. The smoke test
expects the default local Zotero database at `~/Zotero/zotero.sqlite`, but you
can override paths with environment variables:

```powershell
$env:ZOTERO_EXE = "C:\Program Files\Zotero\zotero.exe"
$env:ZOTERO_DATA_DIR = "$HOME\Zotero"
```

## 2. Install the MCP server

```powershell
cd mcp/zotero-mcp-server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[all]"
```

For local reads only:

```powershell
$env:ZOTERO_LOCAL = "true"
$env:ZOTERO_LOCAL_LIBRARY_ID = "0"
```

For hybrid read/write mode:

```powershell
$env:ZOTERO_LOCAL = "true"
$env:ZOTERO_LOCAL_LIBRARY_ID = "0"
$env:ZOTERO_LIBRARY_ID = "YOUR_ZOTERO_USER_ID"
$env:ZOTERO_LIBRARY_TYPE = "user"
$env:ZOTERO_API_KEY_FILE = "C:\path\outside\repo\zotero_api_key.txt"
```

The local library ID is usually `0`. The Web API library ID is your numeric
zotero.org user ID or group ID.

## 3. Configure Codex or another MCP client

Use `config/codex-config.example.toml` as the starting point. Keep secrets out
of the config; prefer `ZOTERO_API_KEY_FILE`.

## 4. Install the literature review skill

Copy `skills/zotero-literature-review` into your agent's skill directory. The
skill is useful for:

- Zotero-backed literature reviews
- Word bibliography extraction and DOI matching
- creating Zotero collections from reference lists
- checking citations and metadata
- Word dynamic Zotero field insertion workflows
- PDF auto-fetch policy decisions

## 5. Build the Zotero plugin

```powershell
powershell -ExecutionPolicy Bypass -File .\plugins\zotero-auto-pdf-fetch\validate.ps1
powershell -ExecutionPolicy Bypass -File .\plugins\zotero-auto-pdf-fetch\package.ps1
```

Install the `.xpi` in Zotero's Plugin Manager.

## 6. Verify

```powershell
python skills/zotero-literature-review/scripts/run_smoke_test.py
python skills/zotero-literature-review/scripts/run_mcp_smoke_test.py
powershell -ExecutionPolicy Bypass -File .\scripts\sanitize_check.ps1
```

## 7. PDF automation behavior

MCP `attach_mode="auto"` tries legal/open-access sources. If it finds a PDF URL
but direct download fails, it creates a linked PDF URL attachment. If no
candidate URL is found, no linked attachment is created.

The Zotero plugin is stronger for interactive Zotero workflows because it calls
Zotero's internal `Zotero.Attachments.addAvailableFiles()` from inside Zotero.

