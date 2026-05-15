# Research Skills Codex Package

This package is a portable, topic-neutral Codex project template for scientific research workflows.

It includes skills for literature work, Zotero-assisted review, XRD/GIWAXS/WAXS processing, scientific plotting, band alignment, 1D band diagrams, COMSOL optical/optoelectronic simulation, interface band-offset workflows, photodetector metric analysis, Origin Pro MCP automation, and research-pipeline setup.

It is **not preconfigured for any specific research topic**. After installation, fill `PROJECT_VARIABLES.md` and, when relevant, `DEVICE_CONFIG.md` with the installing user's own research details.

## Contents

- `AGENTS.md`: active topic-neutral Codex project instruction file.
- `PROJECT_VARIABLES.md`: required user project variables.
- `DEVICE_CONFIG.md`: generic device/sample/system configuration template.
- `MEMORY.md`: empty durable memory scaffold.
- `memory/`: project-local daily notes directory.
- `skills/`: bundled research skills with scripts, references, and vendor dependencies where present.
- `scripts/`: reusable helper scripts.
- `examples/project-template/`: generic project configuration examples.
- `config/mcporter.template.json`: Origin Pro and Zotero MCP configuration template.
- `install.ps1`: copy this package into another Codex project.
- `setup-origin-pro-mcp.ps1`: install and configure the Origin Pro MCP server for the target machine.
- `setup-zotero-mcp.ps1`: install and configure the Zotero MCP server for the target machine.
- `mcp/zotero-mcp-server/`: Zotero MCP server source for local/hybrid Zotero access.
- `plugins/zotero-auto-pdf-fetch/`: Zotero plugin source that auto-runs Zotero's internal available-file finder for newly added items.
- `docs/ZOTERO_USAGE.*.md`: bilingual Zotero setup and use guide.
- `verify-package.ps1`: check that required files and skills exist.
- `manifest.json`: package inventory.

## Install Into Another Codex Project

From PowerShell:

```powershell
Set-Location path\to\research-skills-codex-package
.\install.ps1 -TargetProject "D:\your-codex-project"
```

Existing files are not overwritten unless you pass `-Force`:

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project" -Force
```

The installer copies skills into the target project. It does not install them into the global Codex skill directory.

## Enable Origin Pro MCP

On the target Windows computer, make sure Origin Pro 2020+ is installed. Then run:

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project" -SetupOriginProMcp
```

Or, after installation:

```powershell
Set-Location "D:\your-codex-project"
.\setup-origin-pro-mcp.ps1
```

If Python is not on `PATH`, pass the Windows Python executable explicitly:

```powershell
.\setup-origin-pro-mcp.ps1 -Python "C:\Path\To\python.exe"
```

The setup script installs `skills/origin-pro-mcp` as an editable Python package, verifies `mcp`, `pywin32`, and `Pillow`, and writes a path-correct `config/mcporter.json`. Start Origin Pro before using the MCP server.

## Enable Zotero MCP

On the target computer, install Zotero Desktop first. For read-only local workflows, run:

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project" -SetupZoteroMcp -ZoteroLocalOnly
```

For hybrid read/write workflows, create a Zotero API key at `https://www.zotero.org/settings/keys`, save it in a file outside the project, then run:

```powershell
.\install.ps1 `
  -TargetProject "D:\your-codex-project" `
  -SetupZoteroMcp `
  -ZoteroLibraryId "YOUR_ZOTERO_USER_OR_GROUP_ID" `
  -ZoteroApiKeyFile "C:\Path\Outside\Project\zotero_api_key.txt"
```

Or, after installation:

```powershell
Set-Location "D:\your-codex-project"
.\setup-zotero-mcp.ps1 -ZoteroLocalOnly
```

The setup script creates `mcp/zotero-mcp-server/.venv`, installs the server as an editable Python package, verifies imports, and adds a `zotero` entry to `config/mcporter.json`. It references the Zotero API key by file path and does not copy the key into the project.

## Build Zotero Auto PDF Fetch Plugin

After installation, build the Zotero plugin from the target project:

```powershell
Set-Location "D:\your-codex-project"
powershell -ExecutionPolicy Bypass -File .\plugins\zotero-auto-pdf-fetch\validate.ps1
powershell -ExecutionPolicy Bypass -File .\plugins\zotero-auto-pdf-fetch\package.ps1
```

Install the generated `.xpi` from Zotero's `Tools -> Plugins -> Install Add-on From File...`.

By default the plugin uses Zotero's legal `doi,url,oa` available-file methods and disables custom resolvers.

## Configure The User Project

After installation, edit:

```text
PROJECT_VARIABLES.md
DEVICE_CONFIG.md
```

At minimum, configure:

- project title and research field
- material, sample, device, or system structure
- primary objectives
- key characterization methods and data types
- simulation scope and software environment
- validation criteria and output style

If these values remain `<UNCONFIGURED>`, the assistant should ask for them before making topic-specific assumptions.

## Verify

Verify the package itself:

```powershell
.\verify-package.ps1
```

After installing into another project:

```powershell
.\verify-package.ps1 -Root "D:\your-codex-project"
```

## Notes

- This package intentionally removes source-workspace topic content, historical memories, local project paths, measured claims, and dedicated research examples.
- Large scientific skills include vendored Python dependencies, so the offline package can be large but more portable.
- COMSOL-related workflows still require a valid local COMSOL installation, license, and required modules on the target computer.
- Origin Pro MCP requires a valid Origin Pro installation and Windows COM availability on the target computer.
- Zotero MCP requires Zotero Desktop for local reads and a user-provided Zotero Web API key for write tools.
- For quantitative simulation, configure material parameters and measurement conditions before treating outputs as final.
