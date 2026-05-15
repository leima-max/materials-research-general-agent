# Packaging Report

Date: 2026-05-11

Package path:

```text
<PACKAGE_ROOT>
```

## Update Summary

The package has been genericized into a topic-neutral research skills package.

Applied cleanup:

- Removed source-project historical `memory/` contents.
- Removed source-project `examples/` and replaced them with generic project templates.
- Removed COMSOL skill outputs, logs, and source-project simulation configuration JSON files.
- Replaced active identity/configuration files with generic research-skill instructions.
- Added `PROJECT_VARIABLES.md` to make the user's own research context explicit and required.
- Replaced device/sample defaults with placeholder variables in `DEVICE_CONFIG.md`.

## Active Install Behavior

`install.ps1` copies the package into a target Codex project and keeps bundled skills project-local. It does not install skills into a global Codex skill directory.

After installation, users must configure:

```text
PROJECT_VARIABLES.md
DEVICE_CONFIG.md
```

## Verification

Run:

```powershell
.\verify-package.ps1
```

Expected result:

- required active files exist
- `skills/` contains 12 required skill directories with `SKILL.md`
- `examples/project-template/` exists
- `memory/` exists as an empty project-local notes area
- `config/mcporter.template.json` exists for Origin Pro MCP setup

## Origin Pro MCP Update

Added `skills/origin-pro-mcp` plus:

- `setup-origin-pro-mcp.ps1`
- `config/mcporter.template.json`
- package metadata and verification coverage

The setup script installs the MCP server as an editable Python package, verifies `mcp`, `pywin32`, and `Pillow`, and generates a target-machine `config/mcporter.json`. Origin Pro itself is not bundled; it must be installed and running on the target Windows machine.

## Zotero Complete Workflow Update

Added and sanitized the full Zotero workflow stack:

- replaced `skills/zotero-literature-review` with a clean generic skill
- added `mcp/zotero-mcp-server` with local/hybrid Zotero MCP source
- added `plugins/zotero-auto-pdf-fetch` with Zotero 7/8 plugin source
- added `setup-zotero-mcp.ps1`
- added `config/zotero-mcp.env.example`
- added `config/zotero-codex-config.example.toml`
- expanded `config/mcporter.template.json` with a Zotero MCP server template
- added bilingual usage docs under `docs/ZOTERO_USAGE.*.md`
- added `scripts/sanitize-zotero-package.ps1`

Sensitive Zotero data is intentionally excluded: API keys, real user/library IDs, live collection/item keys, Zotero databases, private PDFs, generated XPI files, and source-machine local paths.

## Notes

- No specific research topic, measured claim, material stack, local COMSOL path, or source-workspace memory should be treated as configured.
- Quantitative simulation requires user-provided material parameters, boundary conditions, measurement conditions, and validation criteria.

