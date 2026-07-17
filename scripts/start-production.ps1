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

& (Join-Path $PSScriptRoot "check-mvp-readiness.ps1")
if ($LASTEXITCODE -ne 0) { throw "MVP production configuration is incomplete" }

$publicUri = [Uri]$settings["PUBLIC_BASE_URL"]
if (Get-NetTCPConnection -State Listen -LocalPort 3000, 8000 -ErrorAction SilentlyContinue) {
    throw "Ports 3000 or 8000 are already in use"
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
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    } finally {
        Remove-Item Env:INTERNAL_API_BASE_URL -ErrorAction SilentlyContinue
        Pop-Location
    }
}

$backendEnvironment = @{
    DATABASE_URL = "sqlite:///./dev.db"
    ENVIRONMENT = "production"
    AI_PROVIDER = "local"
    HF_HUB_DISABLE_XET = "1"
    AUTH_SECRET_KEY = $settings["AUTH_SECRET_KEY"]
    AUTH_COOKIE_SECURE = "true"
    BOOTSTRAP_ADMIN_PASSWORD = $settings["BOOTSTRAP_ADMIN_PASSWORD"]
    SMTP_HOST = $(if ($settings["SMTP_HOST"]) { $settings["SMTP_HOST"] } else { "smtp.qq.com" })
    SMTP_PORT = $(if ($settings["SMTP_PORT"]) { $settings["SMTP_PORT"] } else { "465" })
    SMTP_USERNAME = $settings["SMTP_USERNAME"]
    SMTP_AUTHORIZATION_CODE = $settings["SMTP_AUTHORIZATION_CODE"]
    SMTP_SENDER_NAME = $(if ($settings["SMTP_SENDER_NAME"]) { $settings["SMTP_SENDER_NAME"] } else { "CareerPilot AI" })
    SMTP_USE_SSL = $(if ($settings["SMTP_USE_SSL"]) { $settings["SMTP_USE_SSL"] } else { "true" })
}
if ($settings["BROWSER_PROXY_URL"]) { $backendEnvironment.BROWSER_PROXY_URL = $settings["BROWSER_PROXY_URL"] }

$backend = Start-WithEnvironment -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", "& '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000") -Environment $backendEnvironment -WorkingDirectory (Join-Path $root "backend") -StandardOutput (Join-Path $runtimeDir "backend.log") -StandardError (Join-Path $runtimeDir "backend-error.log")
$frontend = Start-WithEnvironment -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", "& '$node' node_modules\next\dist\bin\next start --hostname 127.0.0.1 --port 3000") -Environment @{ INTERNAL_API_BASE_URL = "http://127.0.0.1:8000" } -WorkingDirectory (Join-Path $root "frontend") -StandardOutput (Join-Path $runtimeDir "frontend.log") -StandardError (Join-Path $runtimeDir "frontend-error.log")

$tunnelLog = Join-Path $runtimeDir "cloudflared-production.log"
$tunnelError = Join-Path $runtimeDir "cloudflared-production-error.log"
$tunnelEnvironment = @{ TUNNEL_TOKEN = $settings["CLOUDFLARE_TUNNEL_TOKEN"] }
if ($settings["OUTBOUND_HTTPS_PROXY"]) {
    $tunnelEnvironment.HTTP_PROXY = $settings["OUTBOUND_HTTPS_PROXY"]
    $tunnelEnvironment.HTTPS_PROXY = $settings["OUTBOUND_HTTPS_PROXY"]
}
$tunnel = Start-WithEnvironment -FilePath $cloudflared -ArgumentList @("tunnel", "run", "--no-autoupdate") -Environment $tunnelEnvironment -WorkingDirectory $root -StandardOutput $tunnelLog -StandardError $tunnelError

[System.IO.File]::WriteAllText((Join-Path $runtimeDir "online-pids.json"), (@{
    backend = $backend.Id
    frontend = $frontend.Id
    tunnel = $tunnel.Id
} | ConvertTo-Json))
[System.IO.File]::WriteAllText((Join-Path $runtimeDir "public-url.txt"), $publicUri.GetLeftPart([UriPartial]::Authority))

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3
        if ($health.status -eq "ok") { break }
    } catch {
        if ($attempt -eq 29) { throw "Backend health check failed" }
    }
}

Write-Output $publicUri.GetLeftPart([UriPartial]::Authority)
