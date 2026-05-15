$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $root "src"
$manifestPath = Join-Path $src "manifest.json"
$bootstrapPath = Join-Path $src "bootstrap.js"
$prefsPath = Join-Path $src "prefs.js"

foreach ($path in @($manifestPath, $bootstrapPath, $prefsPath)) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Missing required plugin file: $path"
  }
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.manifest_version -ne 2) {
  throw "manifest_version must be 2"
}
if ($manifest.applications.zotero.id -ne "zoteroautopdffetch@openclaw.org") {
  throw "Unexpected Zotero plugin id"
}
if (-not $manifest.applications.zotero.strict_min_version) {
  throw "Missing strict_min_version"
}

$bootstrap = Get-Content -LiteralPath $bootstrapPath -Raw
foreach ($needle in @(
  "Zotero.Notifier.registerObserver",
  "Zotero.Notifier.unregisterObserver",
  "Zotero.Attachments.addAvailableFiles",
  "Zotero.Attachments.canFindFileForItem"
)) {
  if (-not $bootstrap.Contains($needle)) {
    throw "bootstrap.js is missing required code: $needle"
  }
}

$prefs = Get-Content -LiteralPath $prefsPath -Raw
if (-not $prefs.Contains('pref("extensions.zotero-auto-pdf-fetch.includeCustomResolvers", false);')) {
  throw "Default custom resolver safety preference must be false"
}
if (-not $prefs.Contains('pref("extensions.zotero-auto-pdf-fetch.methods", "doi,url,oa");')) {
  throw "Default resolver methods must be doi,url,oa"
}

Write-Output "Plugin source validation passed."
