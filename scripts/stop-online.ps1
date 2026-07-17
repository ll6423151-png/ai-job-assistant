$root = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $root "runtime\online-pids.json"
if (-not (Test-Path -LiteralPath $pidPath)) { return }
$processes = ConvertFrom-Json ([System.IO.File]::ReadAllText($pidPath))
foreach ($processId in @($processes.backend, $processes.frontend, $processes.tunnel)) {
    if ($processId) { Stop-Process -Id $processId -ErrorAction SilentlyContinue }
}
foreach ($port in @(3000, 8000)) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Stop-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    }
}
Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
