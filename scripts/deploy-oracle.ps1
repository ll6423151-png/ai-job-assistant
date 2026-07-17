param(
    [Parameter(Mandatory = $true)][string]$ServerHost,
    [string]$SshUser = "ubuntu",
    [Parameter(Mandatory = $true)][string]$Domain,
    [Parameter(Mandatory = $true)][string]$CertificateEmail,
    [Parameter(Mandatory = $true)][string]$RepositoryUrl,
    [Parameter(Mandatory = $true)][string]$AdminPassword,
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\id_rsa",
    [string]$PostgresPassword,
    [string]$AuthSecret
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$ssh = Get-Command ssh.exe -ErrorAction Stop
$scp = Get-Command scp.exe -ErrorAction Stop

function New-HexSecret([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

if (-not (Test-Path -LiteralPath $SshKeyPath)) { throw "SSH key not found: $SshKeyPath" }
if ($Domain -notmatch '^[A-Za-z0-9.-]+$' -or $Domain.EndsWith(".invalid")) { throw "Domain is invalid" }
if ($ServerHost -notmatch '^[A-Za-z0-9.:-]+$') { throw "ServerHost is invalid" }
if ($SshUser -notmatch '^[A-Za-z0-9_-]+$') { throw "SshUser is invalid" }
if ($CertificateEmail -notmatch '^[^\s@]+@[^\s@]+$') { throw "CertificateEmail is invalid" }
if ($RepositoryUrl -notmatch '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$') { throw "RepositoryUrl must be a public GitHub HTTPS repository" }
if ($AdminPassword.Length -lt 12 -or $AdminPassword -notmatch '^[A-Za-z0-9._-]+$') { throw "AdminPassword must be at least 12 characters using letters, numbers, dot, underscore or hyphen" }
if (-not $PostgresPassword) { $PostgresPassword = New-HexSecret 24 }
if ($PostgresPassword -notmatch '^[A-Za-z0-9]+$') { throw "PostgresPassword must be alphanumeric for DATABASE_URL safety" }
if (-not $AuthSecret) { $AuthSecret = New-HexSecret 48 }

$remote = "$SshUser@$ServerHost"
$staging = Join-Path $env:TEMP ("careerpilot-oracle-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $staging | Out-Null
try {
    $envFile = @"
POSTGRES_USER=jobai
POSTGRES_PASSWORD=$PostgresPassword
POSTGRES_DB=jobai
DATABASE_URL=postgresql+psycopg://jobai:$PostgresPassword@postgres:5432/jobai
REDIS_URL=redis://redis:6379/0
BACKEND_CORS_ORIGINS=https://$Domain
AI_PROVIDER=local
LOCAL_TRANSCRIPTION_MODEL=base
RESUME_UPLOAD_MAX_MB=8
AUDIO_UPLOAD_MAX_MB=12
BROWSER_PROXY_URL=http://127.0.0.1:3456
BROWSER_PROXY_TIMEOUT_SECONDS=20
APPLICATION_AUTOMATION_DAILY_LIMIT=20
APPLICATION_AUTOMATION_COOLDOWN_SECONDS=60
AUTH_SECRET_KEY=$AuthSecret
AUTH_COOKIE_NAME=careerpilot_session
AUTH_SESSION_DAYS=30
AUTH_IDLE_MINUTES=120
AUTH_COOKIE_SECURE=true
BOOTSTRAP_ADMIN_ENABLED=true
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=$AdminPassword
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=
SMTP_AUTHORIZATION_CODE=
SMTP_SENDER_NAME=CareerPilot AI
SMTP_USE_SSL=true
PUBLIC_BASE_URL=https://$Domain
"@
    $envPath = Join-Path $staging "careerpilot.env.oracle"
    [IO.File]::WriteAllText($envPath, $envFile, (New-Object Text.UTF8Encoding($false)))
    & $scp.Source -i $SshKeyPath (Join-Path $root "deploy\oracle\bootstrap.sh") "$remote`:/tmp/careerpilot-bootstrap.sh"
    if ($LASTEXITCODE -ne 0) { throw "Failed to upload bootstrap script" }
    & $scp.Source -i $SshKeyPath $envPath "$remote`:/tmp/careerpilot.env.oracle"
    if ($LASTEXITCODE -ne 0) { throw "Failed to upload private environment file" }
    & $ssh.Source -i $SshKeyPath $remote "chmod +x /tmp/careerpilot-bootstrap.sh && bash /tmp/careerpilot-bootstrap.sh '$Domain' '$RepositoryUrl' '$CertificateEmail'"
    if ($LASTEXITCODE -ne 0) { throw "Oracle bootstrap failed" }
} finally {
    if ($staging.StartsWith($env:TEMP, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $staging)) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
