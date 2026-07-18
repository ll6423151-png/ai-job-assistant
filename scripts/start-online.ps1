param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root ".env.online"
$runtimeDir = Join-Path $root "runtime"
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
$node = "C:\Users\33387\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$cloudflared = Join-Path $root "tools\cloudflared.exe"

if (-not (Test-Path -LiteralPath $configPath)) { throw "Missing .env.online" }
if (-not (Test-Path -LiteralPath $python)) { throw "Missing backend Python environment" }
if (-not (Test-Path -LiteralPath $node)) { throw "Missing bundled Node.js runtime" }
if (-not (Test-Path -LiteralPath $cloudflared)) { throw "Missing tools\cloudflared.exe" }

$settings = @{}
foreach ($line in [System.IO.File]::ReadAllLines($configPath)) {
    if (-not $line -or $line.TrimStart().StartsWith("#")) { continue }
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) { $settings[$parts[0].Trim()] = $parts[1].Trim() }
}

function Start-WithEnvironment {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [hashtable]$Environment,
        [string]$WorkingDirectory,
        [string]$StandardOutput,
        [string]$StandardError
    )
    $previous = @{}
    try {
        foreach ($key in $Environment.Keys) {
            $previous[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
            [Environment]::SetEnvironmentVariable($key, [string]$Environment[$key], "Process")
        }
        $parameters = @{
            FilePath = $FilePath
            ArgumentList = $ArgumentList
            WorkingDirectory = $WorkingDirectory
            WindowStyle = "Hidden"
            PassThru = $true
        }
        if ($StandardOutput) { $parameters.RedirectStandardOutput = $StandardOutput }
        if ($StandardError) { $parameters.RedirectStandardError = $StandardError }
        return Start-Process @parameters
    } finally {
        foreach ($key in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable($key, $previous[$key], "Process")
        }
    }
}

if (-not $settings["AUTH_SECRET_KEY"] -or $settings["AUTH_SECRET_KEY"].Length -lt 32) {
    throw "AUTH_SECRET_KEY with at least 32 characters is required"
}
if (-not $settings["BOOTSTRAP_ADMIN_PASSWORD"] -or $settings["BOOTSTRAP_ADMIN_PASSWORD"] -eq "admin123") {
    throw "Set a non-default BOOTSTRAP_ADMIN_PASSWORD before online startup"
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$previousDatabaseUrl = $env:DATABASE_URL
$previousInitPassword = $env:INIT_USER_PASSWORD
try {
    $env:DATABASE_URL = "sqlite:///./dev.db"
    $env:INIT_USER_PASSWORD = $settings["BOOTSTRAP_ADMIN_PASSWORD"]
    Push-Location (Join-Path $root "backend")
    & $python scripts\init_user.py --username admin --email admin@local.invalid --admin --legacy-owner --update-password
    if ($LASTEXITCODE -ne 0) { throw "Administrator initialization failed" }
} finally {
    Pop-Location
    $env:DATABASE_URL = $previousDatabaseUrl
    $env:INIT_USER_PASSWORD = $previousInitPassword
}

if (-not $SkipBuild) {
    Push-Location (Join-Path $root "frontend")
    try {
        $env:INTERNAL_API_BASE_URL = "http://127.0.0.1:8000"
        & $node "node_modules\next\dist\bin\next" build
    } finally {
        Remove-Item Env:INTERNAL_API_BASE_URL -ErrorAction SilentlyContinue
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
}

$backendEnvironment = @{
    DATABASE_URL = "sqlite:///./dev.db"
    ENVIRONMENT = "production"
    AI_PROVIDER = "local"
    HF_HUB_DISABLE_XET = "1"
    AUTH_SECRET_KEY = $settings["AUTH_SECRET_KEY"]
    AUTH_COOKIE_SECURE = "true"
    BOOTSTRAP_ADMIN_PASSWORD = $settings["BOOTSTRAP_ADMIN_PASSWORD"]
    SMTP_USERNAME = $settings["SMTP_USERNAME"]
    SMTP_AUTHORIZATION_CODE = $settings["SMTP_AUTHORIZATION_CODE"]
    EMAIL_RELAY_TOKEN = $settings["EMAIL_RELAY_TOKEN"]
}
$backend = Start-WithEnvironment -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", "& '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000") -Environment $backendEnvironment -WorkingDirectory (Join-Path $root "backend") -StandardOutput (Join-Path $runtimeDir "backend.log") -StandardError (Join-Path $runtimeDir "backend-error.log")
$frontend = Start-WithEnvironment -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", "& '$node' node_modules\next\dist\bin\next start --hostname 127.0.0.1 --port 3000") -Environment @{ INTERNAL_API_BASE_URL = "http://127.0.0.1:8000" } -WorkingDirectory (Join-Path $root "frontend") -StandardOutput (Join-Path $runtimeDir "frontend.log") -StandardError (Join-Path $runtimeDir "frontend-error.log")

$tunnelLog = Join-Path $runtimeDir "cloudflared.log"
$tunnelError = Join-Path $runtimeDir "cloudflared-error.log"
$tunnelEnvironment = @{}
if ($settings["OUTBOUND_HTTPS_PROXY"]) {
    $tunnelEnvironment.HTTP_PROXY = $settings["OUTBOUND_HTTPS_PROXY"]
    $tunnelEnvironment.HTTPS_PROXY = $settings["OUTBOUND_HTTPS_PROXY"]
}
$tunnel = Start-WithEnvironment -FilePath $cloudflared -ArgumentList @("tunnel", "--url", "http://127.0.0.1:3000", "--no-autoupdate") -Environment $tunnelEnvironment -WorkingDirectory $root -StandardOutput $tunnelLog -StandardError $tunnelError
$relayTunnelLog = Join-Path $runtimeDir "email-relay-cloudflared.log"
$relayTunnelError = Join-Path $runtimeDir "email-relay-cloudflared-error.log"
$relayTunnel = Start-WithEnvironment -FilePath $cloudflared -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate") -Environment $tunnelEnvironment -WorkingDirectory $root -StandardOutput $relayTunnelLog -StandardError $relayTunnelError

[System.IO.File]::WriteAllText((Join-Path $runtimeDir "online-pids.json"), (@{
    backend = $backend.Id
    frontend = $frontend.Id
    tunnel = $tunnel.Id
    relay_tunnel = $relayTunnel.Id
} | ConvertTo-Json))

$publicUrl = $null
function Read-SharedText([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return "" }
    $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $reader = New-Object System.IO.StreamReader($stream)
        try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally { $stream.Dispose() }
}
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Seconds 1
    $content = (Read-SharedText $tunnelLog) + (Read-SharedText $tunnelError)
    $match = [regex]::Match($content, "https://[a-z0-9-]+\.trycloudflare\.com")
    if ($match.Success) { $publicUrl = $match.Value; break }
}

if (-not $publicUrl) { throw "Tunnel started but no public URL was found. Check runtime logs." }
[System.IO.File]::WriteAllText((Join-Path $runtimeDir "public-url.txt"), $publicUrl)
$relayPublicUrl = $null
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Seconds 1
    $content = (Read-SharedText $relayTunnelLog) + (Read-SharedText $relayTunnelError)
    $match = [regex]::Match($content, "https://[a-z0-9-]+\.trycloudflare\.com")
    if ($match.Success) { $relayPublicUrl = $match.Value; break }
}
if (-not $relayPublicUrl) { throw "Email relay tunnel started but no public URL was found." }
[System.IO.File]::WriteAllText((Join-Path $runtimeDir "email-relay-public-url.txt"), $relayPublicUrl)
Write-Output $publicUrl
Write-Output "Email relay tunnel is ready."
