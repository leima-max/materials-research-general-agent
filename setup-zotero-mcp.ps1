param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$Python = "",
    [switch]$SkipPipInstall,
    [switch]$LocalOnly,
    [string]$ZoteroLibraryId = "",
    [string]$ZoteroLibraryType = "user",
    [string]$ZoteroApiKeyFile = ""
)

$ErrorActionPreference = "Stop"

$Root = [System.IO.Path]::GetFullPath($Root)
$ServerDir = Join-Path $Root "mcp\zotero-mcp-server"
$PyProject = Join-Path $ServerDir "pyproject.toml"
$ConfigDir = Join-Path $Root "config"
$ConfigPath = Join-Path $ConfigDir "mcporter.json"
$VenvPython = Join-Path $ServerDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PyProject)) {
    throw "Zotero MCP server not found: $PyProject"
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "python.exe not found on PATH. Pass -Python with a Python 3.10+ path."
    }
    $Python = $pythonCmd.Source
}

$Python = [System.IO.Path]::GetFullPath($Python)
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python path does not exist: $Python"
}

$version = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Zotero MCP requires Python 3.10+. Detected: $version"
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $Python -m venv (Join-Path $ServerDir ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment under $ServerDir"
    }
}

if (-not $SkipPipInstall) {
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed in Zotero MCP virtual environment."
    }
    & $VenvPython -m pip install -e "$ServerDir[all]"
    if ($LASTEXITCODE -ne 0) {
        throw "pip install -e `"$ServerDir[all]`" failed."
    }
}

& $VenvPython -c "import mcp, pyzotero, zotero_mcp; print('Zotero MCP Python dependencies OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Dependency import check failed. Run this script without -SkipPipInstall."
}

if (-not $LocalOnly) {
    if ([string]::IsNullOrWhiteSpace($ZoteroLibraryId)) {
        Write-Host "No -ZoteroLibraryId supplied. Configuring local-read mode only."
        Write-Host "For hybrid writes, rerun with -ZoteroLibraryId and -ZoteroApiKeyFile."
        $LocalOnly = $true
    }
    if (-not [string]::IsNullOrWhiteSpace($ZoteroApiKeyFile)) {
        $ZoteroApiKeyFile = [System.IO.Path]::GetFullPath($ZoteroApiKeyFile)
        if (-not (Test-Path -LiteralPath $ZoteroApiKeyFile)) {
            throw "Zotero API key file does not exist: $ZoteroApiKeyFile"
        }
    }
}

New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

$servers = [ordered]@{}
if (Test-Path -LiteralPath $ConfigPath) {
    $existing = Get-Content -Raw -LiteralPath $ConfigPath -Encoding UTF8 | ConvertFrom-Json
    if ($existing.mcpServers) {
        foreach ($prop in $existing.mcpServers.PSObject.Properties) {
            $servers[$prop.Name] = $prop.Value
        }
    }
}

$envSettings = [ordered]@{
    ZOTERO_LOCAL = "true"
    ZOTERO_LOCAL_LIBRARY_ID = "0"
    ZOTERO_LIBRARY_TYPE = $ZoteroLibraryType
    ZOTERO_NO_CLAUDE = "true"
    PYTHONUTF8 = "1"
    PYTHONIOENCODING = "utf-8"
    FASTMCP_SHOW_SERVER_BANNER = "false"
    FASTMCP_CHECK_FOR_UPDATES = "off"
    FASTMCP_ENABLE_RICH_LOGGING = "false"
    FASTMCP_ENABLE_RICH_TRACEBACKS = "false"
    FASTMCP_LOG_LEVEL = "ERROR"
    NO_COLOR = "1"
    TERM = "dumb"
}

if (-not $LocalOnly) {
    $envSettings["ZOTERO_LIBRARY_ID"] = $ZoteroLibraryId
    if (-not [string]::IsNullOrWhiteSpace($ZoteroApiKeyFile)) {
        $envSettings["ZOTERO_API_KEY_FILE"] = $ZoteroApiKeyFile
    }
}

$servers["zotero"] = [ordered]@{
    command = $VenvPython
    args = @("-m", "zotero_mcp.cli", "serve")
    cwd = $ServerDir
    env = $envSettings
    description = "Zotero MCP server. Local reads use Zotero Desktop; hybrid writes require ZoteroLibraryId and ZoteroApiKeyFile."
}

$config = [ordered]@{ mcpServers = $servers }
$config | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

Write-Host "Zotero MCP setup complete."
Write-Host "Python: $VenvPython"
Write-Host "Server: $ServerDir"
Write-Host "MCP config: $ConfigPath"
if ($LocalOnly) {
    Write-Host "Mode: local read mode. Configure Zotero API credentials later for write tools."
} else {
    Write-Host "Mode: hybrid mode. API key is referenced by file path and was not copied into this package."
}
