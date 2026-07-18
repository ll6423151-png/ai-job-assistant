$root = Split-Path -Parent $PSScriptRoot
$urlPath = Join-Path $root "runtime\public-url.txt"
$relayUrlPath = Join-Path $root "runtime\email-relay-public-url.txt"
$pidPath = Join-Path $root "runtime\online-pids.json"
$publicUrl = if (Test-Path -LiteralPath $urlPath) { [System.IO.File]::ReadAllText($urlPath).Trim() } else { "not-created" }
$relayPublicUrl = if (Test-Path -LiteralPath $relayUrlPath) { [System.IO.File]::ReadAllText($relayUrlPath).Trim() } else { "not-created" }
$listeners = Get-NetTCPConnection -State Listen -LocalPort 3000, 8000 -ErrorAction SilentlyContinue
$pids = if (Test-Path -LiteralPath $pidPath) { ConvertFrom-Json ([System.IO.File]::ReadAllText($pidPath)) } else { $null }
[pscustomobject]@{
    PublicUrl = $publicUrl
    EmailRelayUrl = $relayPublicUrl
    Frontend = if ($listeners.LocalPort -contains 3000) { "running" } else { "stopped" }
    Backend = if ($listeners.LocalPort -contains 8000) { "running" } else { "stopped" }
    Tunnel = if ($pids -and (Get-Process -Id $pids.tunnel -ErrorAction SilentlyContinue)) { "running" } else { "stopped" }
    EmailRelayTunnel = if ($pids -and (Get-Process -Id $pids.relay_tunnel -ErrorAction SilentlyContinue)) { "running" } else { "stopped" }
} | Format-List
