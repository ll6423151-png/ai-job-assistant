param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$jdkRoot = Join-Path $root "tools\android-build\jdk"
$keytool = Join-Path $jdkRoot "bin\keytool.exe"
$keystoreDir = Join-Path $root "android\keystore"
$keystoreFile = Join-Path $keystoreDir "careerpilot-release.jks"
$propertiesFile = Join-Path $keystoreDir "keystore.properties"

if (-not (Test-Path -LiteralPath $keytool)) { throw "Android JDK is not installed. Run install-android-toolchain.ps1 first." }
if ((Test-Path -LiteralPath $keystoreFile) -and (Test-Path -LiteralPath $propertiesFile) -and -not $Force) {
    Write-Output "Android release keystore already exists"
    exit 0
}

New-Item -ItemType Directory -Force -Path $keystoreDir | Out-Null
if ($Force) {
    Remove-Item -LiteralPath $keystoreFile,$propertiesFile -Force -ErrorAction SilentlyContinue
}

$bytes = New-Object byte[] 30
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $random.GetBytes($bytes) } finally { $random.Dispose() }
$password = [Convert]::ToBase64String($bytes).Replace("/", "A").Replace("+", "B").TrimEnd("=")
$alias = "careerpilot"

& $keytool -genkeypair -v -keystore $keystoreFile -storepass $password -keypass $password -alias $alias -keyalg RSA -keysize 3072 -validity 10000 -dname "CN=CareerPilot AI, OU=Android, O=CareerPilot AI, L=Chongqing, ST=Chongqing, C=CN"
if ($LASTEXITCODE -ne 0) { throw "Release keystore generation failed" }

$properties = @(
    "storeFile=careerpilot-release.jks"
    "storePassword=$password"
    "keyAlias=$alias"
    "keyPassword=$password"
) -join "`r`n"
[System.IO.File]::WriteAllText($propertiesFile, "$properties`r`n", [System.Text.UTF8Encoding]::new($false))
Write-Output "Android release keystore created at $keystoreFile"
Write-Output "Keep the ignored android/keystore directory for future app updates."
