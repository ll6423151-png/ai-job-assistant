param(
    [string]$BaseUrl = "https://careerpilot-web-33387.onrender.com"
)

$ErrorActionPreference = "Stop"
$uri = [Uri]$BaseUrl
if ($uri.Scheme -ne "https" -or -not $uri.Host.EndsWith(".onrender.com")) {
    throw "BaseUrl must be the deployed Render HTTPS URL"
}
& (Join-Path $PSScriptRoot "build-android.ps1") -ServerUrl $BaseUrl
if ($LASTEXITCODE -ne 0) { throw "Free test APK build failed" }
Write-Output (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\android\CareerPilot-AI-release.apk")
