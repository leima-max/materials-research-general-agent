param(
  [string]$Version = "0.1.8"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $root "src"
$dist = Join-Path $root "dist"
$out = Join-Path $dist "zotero-auto-pdf-fetch-$Version.xpi"

if (-not (Test-Path -LiteralPath $src)) {
  throw "Missing source directory: $src"
}

New-Item -ItemType Directory -Force -Path $dist | Out-Null

if (Test-Path -LiteralPath $out) {
  Remove-Item -LiteralPath $out -Force
}
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcFull = [System.IO.Path]::GetFullPath($src)
$outFull = [System.IO.Path]::GetFullPath($out)
$files = Get-ChildItem -LiteralPath $srcFull -Recurse -File
if (-not $files) {
  throw "No source files found under $srcFull"
}

$archive = [System.IO.Compression.ZipFile]::Open($outFull, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  foreach ($file in $files) {
    $fileFull = [System.IO.Path]::GetFullPath($file.FullName)
    if (-not $fileFull.StartsWith($srcFull, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Refusing to package file outside source directory: $fileFull"
    }
    $relative = $fileFull.Substring($srcFull.Length).TrimStart([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $entryName = $relative.Replace('\', '/')
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
      $archive,
      $fileFull,
      $entryName,
      [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
  }
}
finally {
  $archive.Dispose()
}

Get-FileHash -Algorithm SHA256 -LiteralPath $out |
  Select-Object Path, Hash, @{Name="Length"; Expression={(Get-Item -LiteralPath $out).Length}} |
  Format-List
