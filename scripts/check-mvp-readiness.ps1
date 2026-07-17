$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root ".env.online"

if (-not (Test-Path -LiteralPath $configPath)) { throw "Missing .env.online" }

$settings = @{}
foreach ($line in [System.IO.File]::ReadAllLines($configPath)) {
    if (-not $line -or $line.TrimStart().StartsWith("#")) { continue }
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) { $settings[$parts[0].Trim()] = $parts[1].Trim() }
}

$publicUri = $null
$validPublicUrl = $false
try {
    $publicUri = [Uri]$settings["PUBLIC_BASE_URL"]
    $validPublicUrl = $publicUri.IsAbsoluteUri -and
        $publicUri.Scheme -eq "https" -and
        $publicUri.Host -notin @("localhost", "127.0.0.1") -and
        -not $publicUri.Host.EndsWith(".trycloudflare.com")
} catch {
    $validPublicUrl = $false
}

$checks = @(
    [pscustomobject]@{ Check = "Fixed HTTPS domain"; Ready = $validPublicUrl }
    [pscustomobject]@{ Check = "Cloudflare Named Tunnel token"; Ready = [bool]($settings["CLOUDFLARE_TUNNEL_TOKEN"] -and $settings["CLOUDFLARE_TUNNEL_TOKEN"].Length -ge 20) }
    [pscustomobject]@{ Check = "Authentication secret"; Ready = [bool]($settings["AUTH_SECRET_KEY"] -and $settings["AUTH_SECRET_KEY"].Length -ge 32 -and $settings["AUTH_SECRET_KEY"] -ne "change-this-development-auth-secret") }
    [pscustomobject]@{ Check = "Non-default administrator password"; Ready = [bool]($settings["BOOTSTRAP_ADMIN_PASSWORD"] -and $settings["BOOTSTRAP_ADMIN_PASSWORD"] -ne "admin123") }
    [pscustomobject]@{ Check = "QQ SMTP sender"; Ready = [bool]($settings["SMTP_USERNAME"] -and $settings["SMTP_USERNAME"].EndsWith("@qq.com")) }
    [pscustomobject]@{ Check = "QQ SMTP authorization code"; Ready = [bool]$settings["SMTP_AUTHORIZATION_CODE"] }
)

$checks | Format-Table Check, Ready -AutoSize
if ($checks.Ready -contains $false) { exit 1 }
Write-Output "MVP production configuration is ready"
