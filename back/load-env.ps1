param([string]$Path = ".env")
if (-not (Test-Path $Path)) { Write-Error "Missing $Path"; exit 1 }
Get-Content $Path | ForEach-Object {
  if ($_ -match "^\s*#" -or $_ -match "^\s*$") { return }
  $parts = $_ -split "=", 2
  if ($parts.Length -ne 2) { return }
  $name = $parts[0].Trim()
  $val  = $parts[1].Trim().Trim('"')
  if ($name) { Set-Item -Path ("Env:{0}" -f $name) -Value $val }
}
"QDRANT_URL        = $($env:QDRANT_URL)"
"QDRANT_COLLECTION = $($env:QDRANT_COLLECTION)"
if ($env:QDRANT_API_KEY) { "QDRANT_API_KEY prefix = $($env:QDRANT_API_KEY.Substring(0,8))…" }
