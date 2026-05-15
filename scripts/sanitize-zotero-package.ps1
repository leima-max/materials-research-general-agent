$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$patterns = @(
  "ZOTERO_API_KEY\s*=\s*['\""]?[A-Za-z0-9_\-]{20,}",
  "OPENAI_API_KEY\s*=\s*['\""]?sk-[A-Za-z0-9_\-]{20,}",
  "GEMINI_API_KEY\s*=\s*['\""]?[A-Za-z0-9_\-]{20,}",
  "KIMI_API_KEY\s*=\s*['\""]?[A-Za-z0-9_\-]{20,}",
  "DEEPSEEK_API_KEY\s*=\s*['\""]?[A-Za-z0-9_\-]{20,}",
  "ZOTERO_LIBRARY_ID\s*=\s*['\""]?(?!0\b)\d{4,}['\""]?",
  "gho_[A-Za-z0-9_]{20,}",
  "ghp_[A-Za-z0-9_]{20,}",
  "BEGIN (RSA|OPENSSH|PRIVATE) KEY",
  "C:\\Users\\[^\\\r\n\t\""]+\\\.openclaw",
  "C:/Users/[^/\r\n\t\""]+/\\.openclaw",
  "/Users/[^/\r\n\t\""]+/\\.openclaw",
  "xwechat_files",
  "wxid_"
)

$include = @("*.md","*.py","*.ps1","*.js","*.json","*.toml","*.yaml","*.yml","*.txt")
$files = Get-ChildItem -LiteralPath $root -Recurse -File -Include $include |
  Where-Object {
    $_.FullName -notmatch "\\.git\\" -and
    $_.FullName -notmatch "\\.venv\\" -and
    $_.FullName -notmatch "\\__pycache__\\" -and
    $_.FullName -notmatch "\\vendor\\" -and
    $_.FullName -notmatch "\\site-packages\\" -and
    $_.FullName -notmatch "\\node_modules\\" -and
    $_.FullName -ne $PSCommandPath
  }

$hits = @()
foreach ($file in $files) {
  $text = Get-Content -Raw -LiteralPath $file.FullName -Encoding UTF8
  foreach ($pattern in $patterns) {
    if ($text -match $pattern) {
      $hits += [pscustomobject]@{ File = $file.FullName.Substring($root.Length + 1); Pattern = $pattern }
    }
  }
}

if ($hits.Count -gt 0) {
  $hits | Format-Table -AutoSize
  throw "Sanitize check failed: potential secret or local identifier found."
}

Write-Host "Sanitize check passed."
