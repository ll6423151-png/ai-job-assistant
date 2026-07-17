param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$Repository,
    [string]$Title,
    [switch]$IncludeAab
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$gh = Get-Command gh.exe -ErrorAction Stop
if ($Tag -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+(?:[-.][A-Za-z0-9.-]+)?$') { throw "Tag must look like v1.0.0" }
$uri = [Uri]$BaseUrl
if ($uri.Scheme -ne "https" -or -not $uri.Host -or $uri.Host.EndsWith(".invalid")) { throw "BaseUrl must be the fixed HTTPS application URL" }
if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw "Repository must use owner/repo format" }
if (-not $Title) { $Title = "CareerPilot AI $Tag" }

& (Join-Path $PSScriptRoot "build-android.ps1") -ServerUrl $BaseUrl
if ($LASTEXITCODE -ne 0) { throw "Android release build failed" }

$apk = Join-Path $root "dist\android\CareerPilot-AI-release.apk"
$aab = Join-Path $root "dist\android\CareerPilot-AI-release.aab"
& $gh.Source auth status
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated; run gh auth login" }
$assets = @($apk)
if ($IncludeAab) { $assets += $aab }
& $gh.Source release create $Tag @assets --repo $Repository --title $Title --generate-notes
if ($LASTEXITCODE -ne 0) { throw "GitHub release creation failed" }
