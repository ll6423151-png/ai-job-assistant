param(
    [string]$ServerUrl = $env:CAREERPILOT_BASE_URL,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $root "android"
$jdkRoot = Join-Path $root "tools\android-build\jdk"
$sdkRoot = Join-Path $root "tools\android-build\android-sdk"
$gradle = Join-Path $root "tools\android-build\gradle-8.11.1\bin\gradle.bat"
$outputDir = Join-Path $root "dist\android"

if (-not $ServerUrl) { throw "CAREERPILOT_BASE_URL is required" }
$uri = [Uri]$ServerUrl
if ($uri.Scheme -ne "https" -or -not $uri.Host -or $uri.Host -in @("localhost", "127.0.0.1", "10.0.2.2")) {
    throw "Release APK requires a public HTTPS CAREERPILOT_BASE_URL, not localhost"
}
if (-not (Test-Path -LiteralPath $gradle)) { throw "Android toolchain is missing. Run install-android-toolchain.ps1 first." }

$env:JAVA_HOME = $jdkRoot
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:PATH = "$jdkRoot\bin;$sdkRoot\platform-tools;$env:PATH"
if (Test-NetConnection 127.0.0.1 -Port 7990 -InformationLevel Quiet) {
    $env:GRADLE_OPTS = "-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7990 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7990"
}

& (Join-Path $PSScriptRoot "init-android-keystore.ps1")
if ($LASTEXITCODE -ne 0) { throw "Keystore initialization failed" }

if (-not $SkipTests) {
    & $gradle -p $androidRoot testDebugUnitTest lintDebug "-PCAREERPILOT_BASE_URL=$ServerUrl"
    if ($LASTEXITCODE -ne 0) { throw "Android tests or lint failed" }
}

& $gradle -p $androidRoot clean assembleDebug assembleRelease bundleRelease "-PCAREERPILOT_BASE_URL=$ServerUrl"
if ($LASTEXITCODE -ne 0) { throw "Android APK/AAB build failed" }

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
$debugSource = Join-Path $androidRoot "app\build\outputs\apk\debug\app-debug.apk"
$releaseSource = Join-Path $androidRoot "app\build\outputs\apk\release\app-release.apk"
$bundleSource = Join-Path $androidRoot "app\build\outputs\bundle\release\app-release.aab"
$debugTarget = Join-Path $outputDir "CareerPilot-AI-debug.apk"
$releaseTarget = Join-Path $outputDir "CareerPilot-AI-release.apk"
$bundleTarget = Join-Path $outputDir "CareerPilot-AI-release.aab"
Copy-Item -LiteralPath $debugSource -Destination $debugTarget -Force
Copy-Item -LiteralPath $releaseSource -Destination $releaseTarget -Force
Copy-Item -LiteralPath $bundleSource -Destination $bundleTarget -Force

$apksigner = Join-Path $sdkRoot "build-tools\35.0.0\apksigner.bat"
& $apksigner verify --verbose --print-certs $debugTarget
if ($LASTEXITCODE -ne 0) { throw "Debug APK signature verification failed" }
& $apksigner verify --verbose --print-certs $releaseTarget
if ($LASTEXITCODE -ne 0) { throw "Release APK signature verification failed" }

Get-FileHash -LiteralPath $debugTarget,$releaseTarget,$bundleTarget -Algorithm SHA256 | Select-Object Path,Hash
