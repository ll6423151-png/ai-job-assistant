param(
    [string]$Recipient
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root ".env.online"
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $configPath)) { throw "Missing .env.online" }
if (-not (Test-Path -LiteralPath $python)) { throw "Missing backend Python environment" }

$settings = @{}
foreach ($line in [System.IO.File]::ReadAllLines($configPath)) {
    if (-not $line -or $line.TrimStart().StartsWith("#")) { continue }
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) { $settings[$parts[0].Trim()] = $parts[1].Trim() }
}

foreach ($key in @("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_AUTHORIZATION_CODE", "SMTP_SENDER_NAME", "SMTP_USE_SSL")) {
    if ($settings.ContainsKey($key)) {
        [Environment]::SetEnvironmentVariable($key, $settings[$key], "Process")
    }
}

if (-not $settings["SMTP_USERNAME"] -or -not $settings["SMTP_AUTHORIZATION_CODE"]) {
    throw "Configure SMTP_USERNAME and SMTP_AUTHORIZATION_CODE in .env.online"
}

Push-Location (Join-Path $root "backend")
try {
    $arguments = @("-m", "scripts.check_smtp")
    if ($Recipient) { $arguments += @("--recipient", $Recipient) }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "QQ SMTP verification failed" }
} finally {
    Pop-Location
}
