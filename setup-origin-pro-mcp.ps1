param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$Python = "",
    [switch]$SkipPipInstall,
    [switch]$CheckOriginCom
)

$ErrorActionPreference = "Stop"

$Root = [System.IO.Path]::GetFullPath($Root)
$SkillDir = Join-Path $Root "skills\origin-pro-mcp"
$ServerPath = Join-Path $SkillDir "server.py"
$ConfigDir = Join-Path $Root "config"
$ConfigPath = Join-Path $ConfigDir "mcporter.json"

if (-not (Test-Path -LiteralPath $ServerPath)) {
    throw "Origin Pro MCP server not found: $ServerPath"
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "python.exe not found on PATH. Pass -Python with a Windows Python 3.10+ path."
    }
    $Python = $pythonCmd.Source
}

$Python = [System.IO.Path]::GetFullPath($Python)
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python path does not exist: $Python"
}

$version = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Origin Pro MCP requires Python 3.10+. Detected: $version"
}

if (-not $SkipPipInstall) {
    & $Python -m pip install -e $SkillDir
    if ($LASTEXITCODE -ne 0) {
        throw "pip install -e failed for $SkillDir"
    }
}

& $Python -c "import mcp, win32com.client, PIL; print('Origin Pro MCP Python dependencies OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Dependency import check failed. Run this script without -SkipPipInstall or install requirements.txt manually."
}

if ($CheckOriginCom) {
    & $Python -c "import win32com.client; win32com.client.GetActiveObject('Origin.ApplicationSI'); print('Origin Pro COM active object OK')"
    if ($LASTEXITCODE -ne 0) {
        throw "Origin Pro COM check failed. Start Origin Pro first, then rerun with -CheckOriginCom."
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

$servers["origin-pro"] = [ordered]@{
    command = $Python
    args = @("-u", $ServerPath)
    description = "Origin Pro MCP server via Windows COM automation. Start Origin Pro before using this server."
}

$config = [ordered]@{ mcpServers = $servers }
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

Write-Host "Origin Pro MCP setup complete."
Write-Host "Python: $Python"
Write-Host "Server: $ServerPath"
Write-Host "MCP config: $ConfigPath"
Write-Host "Start Origin Pro before launching the MCP server."
