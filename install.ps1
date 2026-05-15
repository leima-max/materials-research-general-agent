param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject,

    [switch]$SetupOriginProMcp,
    [switch]$SetupZoteroMcp,
    [string]$Python = "",
    [switch]$ZoteroLocalOnly,
    [string]$ZoteroLibraryId = "",
    [string]$ZoteroApiKeyFile = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetRoot = [System.IO.Path]::GetFullPath($TargetProject)

function Copy-PathSafely {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (Test-Path -LiteralPath $Destination) {
        if (-not $Force) {
            Write-Host "Skip existing: $Destination"
            return
        }

        $resolvedDestination = [System.IO.Path]::GetFullPath($Destination)
        $resolvedTargetRoot = [System.IO.Path]::GetFullPath($TargetRoot)
        if (-not $resolvedDestination.StartsWith($resolvedTargetRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to overwrite path outside target project: $resolvedDestination"
        }

        Remove-Item -LiteralPath $Destination -Recurse -Force
    }

    $parent = Split-Path -Parent $Destination
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
    Write-Host "Copied: $Destination"
}

if (-not (Test-Path -LiteralPath $TargetRoot)) {
    New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
}

$items = @(
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
    "PACKAGING_REPORT.md",
    "config",
    "docs",
    "mcp",
    "plugins",
    "memory",
    "skills",
    "scripts",
    "examples"
)

foreach ($item in $items) {
    $src = Join-Path $SourceRoot $item
    if (Test-Path -LiteralPath $src) {
        Copy-PathSafely -Source $src -Destination (Join-Path $TargetRoot $item)
    }
}

Write-Host ""
Write-Host "Research skills package installed to: $TargetRoot"
Write-Host "Open that folder as a Codex project so AGENTS.md is active."
Write-Host "Before topic-specific work, fill PROJECT_VARIABLES.md with the user's own research context."

if ($SetupOriginProMcp) {
    $setupScript = Join-Path $TargetRoot "setup-origin-pro-mcp.ps1"
    if ([string]::IsNullOrWhiteSpace($Python)) {
        powershell -ExecutionPolicy Bypass -File $setupScript -Root $TargetRoot
    } else {
        powershell -ExecutionPolicy Bypass -File $setupScript -Root $TargetRoot -Python $Python
    }
}

if ($SetupZoteroMcp) {
    $setupScript = Join-Path $TargetRoot "setup-zotero-mcp.ps1"
    $zoteroSetupArgs = @("-ExecutionPolicy", "Bypass", "-File", $setupScript, "-Root", $TargetRoot)
    if (-not [string]::IsNullOrWhiteSpace($Python)) {
        $zoteroSetupArgs += @("-Python", $Python)
    }
    if ($ZoteroLocalOnly) {
        $zoteroSetupArgs += "-LocalOnly"
    }
    if (-not [string]::IsNullOrWhiteSpace($ZoteroLibraryId)) {
        $zoteroSetupArgs += @("-ZoteroLibraryId", $ZoteroLibraryId)
    }
    if (-not [string]::IsNullOrWhiteSpace($ZoteroApiKeyFile)) {
        $zoteroSetupArgs += @("-ZoteroApiKeyFile", $ZoteroApiKeyFile)
    }
    powershell @zoteroSetupArgs
}
