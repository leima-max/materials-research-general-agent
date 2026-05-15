param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath($Root)

$requiredFiles = @(
    "AGENTS.md",
    "AGENT_COORDINATION.md",
    "PROJECT_VARIABLES.md",
    "DEVICE_CONFIG.md",
    "MEMORY.md",
    "README_INSTALL.md",
    "manifest.json",
    "install.ps1",
    "verify-package.ps1",
    "setup-origin-pro-mcp.ps1",
    "setup-zotero-mcp.ps1",
    "PACKAGING_REPORT.md"
)

$requiredDirs = @(
    "skills",
    "scripts",
    "memory",
    "examples",
    "config",
    "docs",
    "mcp",
    "plugins"
)

$requiredSkills = @(
    "band-align-plot",
    "band-diagram-calc",
    "comsol-opto-simulation",
    "humanizer-1.0.0",
    "interface-band-offset",
    "literature-search",
    "origin-pro-mcp",
    "photodetector-pyradi",
    "pythesis-plot",
    "scientify",
    "xrd-pyfai",
    "zotero-literature-review"
)

$missing = @()
$invalidSkills = @()

foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $file))) {
        $missing += $file
    }
}

foreach ($dir in $requiredDirs) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $dir))) {
        $missing += $dir
    }
}

$skillRoot = Join-Path $Root "skills"
$skills = @()
if (Test-Path -LiteralPath $skillRoot) {
    $skills = Get-ChildItem -Directory -LiteralPath $skillRoot | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md")
    }
}

foreach ($skillName in $requiredSkills) {
    $skillFile = Join-Path (Join-Path $skillRoot $skillName) "SKILL.md"
    if (-not (Test-Path -LiteralPath $skillFile)) {
        $missing += "skills/$skillName/SKILL.md"
        continue
    }

    $skillContent = Get-Content -LiteralPath $skillFile -Encoding UTF8 -TotalCount 40
    if ($skillContent.Count -lt 4 -or $skillContent[0].Trim() -ne "---") {
        $invalidSkills += "skills/$skillName/SKILL.md missing YAML frontmatter"
        continue
    }

    $endIndex = -1
    for ($i = 1; $i -lt $skillContent.Count; $i++) {
        if ($skillContent[$i].Trim() -eq "---") {
            $endIndex = $i
            break
        }
    }

    if ($endIndex -lt 0) {
        $invalidSkills += "skills/$skillName/SKILL.md has unterminated YAML frontmatter"
        continue
    }

    $frontmatter = $skillContent[1..($endIndex - 1)]
    $hasName = $frontmatter | Where-Object { $_ -match '^name:\s*\S+' }
    $hasDescription = $frontmatter | Where-Object { $_ -match '^description:\s*' }
    if (-not $hasName -or -not $hasDescription) {
        $invalidSkills += "skills/$skillName/SKILL.md requires name and description frontmatter"
    }

    $agentYaml = Join-Path (Join-Path (Join-Path $skillRoot $skillName) "agents") "openai.yaml"
    if (-not (Test-Path -LiteralPath $agentYaml)) {
        $invalidSkills += "skills/$skillName/agents/openai.yaml is missing"
    } else {
        $agentContent = Get-Content -LiteralPath $agentYaml -Encoding UTF8
        $hasInterface = $agentContent | Where-Object { $_ -match '^interface:\s*$' }
        $hasDisplayName = $agentContent | Where-Object { $_ -match '^\s+display_name:\s*".+"' }
        $hasShortDescription = $agentContent | Where-Object { $_ -match '^\s+short_description:\s*".+"' }
        $hasDefaultPrompt = $agentContent | Where-Object { $_ -match '^\s+default_prompt:\s*".*\$.+"' }
        if (-not $hasInterface -or -not $hasDisplayName -or -not $hasShortDescription -or -not $hasDefaultPrompt) {
            $invalidSkills += "skills/$skillName/agents/openai.yaml requires interface display_name, short_description, and default_prompt with `$skill"
        }
    }
}

$examplesRoot = Join-Path $Root "examples\project-template"
if (-not (Test-Path -LiteralPath $examplesRoot)) {
    $missing += "examples/project-template"
}

$originTemplate = Join-Path $Root "config\mcporter.template.json"
if (-not (Test-Path -LiteralPath $originTemplate)) {
    $missing += "config/mcporter.template.json"
}

$zoteroRequired = @(
    "config\zotero-mcp.env.example",
    "config\zotero-codex-config.example.toml",
    "docs\ZOTERO_USAGE.en.md",
    "docs\ZOTERO_USAGE.zh-CN.md",
    "mcp\zotero-mcp-server\pyproject.toml",
    "mcp\zotero-mcp-server\src\zotero_mcp\client.py",
    "mcp\zotero-mcp-server\src\zotero_mcp\tools\_helpers.py",
    "plugins\zotero-auto-pdf-fetch\README.md",
    "plugins\zotero-auto-pdf-fetch\package.ps1",
    "plugins\zotero-auto-pdf-fetch\validate.ps1",
    "plugins\zotero-auto-pdf-fetch\src\bootstrap.js",
    "plugins\zotero-auto-pdf-fetch\src\manifest.json",
    "plugins\zotero-auto-pdf-fetch\src\prefs.js",
    "scripts\sanitize-zotero-package.ps1",
    "skills\zotero-literature-review\references\zotero-batch-import.md",
    "skills\zotero-literature-review\references\zotero-pdf-autofetch.md",
    "skills\zotero-literature-review\scripts\run_smoke_test.py",
    "skills\zotero-literature-review\scripts\run_mcp_smoke_test.py"
)

foreach ($item in $zoteroRequired) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $item))) {
        $missing += $item
    }
}

if ($missing.Count -gt 0 -or $invalidSkills.Count -gt 0) {
    Write-Host "Verification failed:"
    $missing | ForEach-Object { Write-Host " - $_" }
    $invalidSkills | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Verification passed: $Root"
Write-Host "Skills found: $($skills.Count)"
$skills | Sort-Object Name | ForEach-Object { Write-Host " - $($_.Name)" }

