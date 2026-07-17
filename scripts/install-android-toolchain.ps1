param(
    [switch]$Force,
    [string]$ProxyUrl = $env:OUTBOUND_HTTPS_PROXY
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$toolRoot = Join-Path $root "tools\android-build"
$runtimeDir = Join-Path $root "runtime\android-toolchain"
$jdkRoot = Join-Path $toolRoot "jdk"
$sdkRoot = Join-Path $toolRoot "android-sdk"
$gradleRoot = Join-Path $toolRoot "gradle-8.11.1"
$jdkArchive = Join-Path $runtimeDir "microsoft-jdk-21-windows-x64.zip"
$sdkArchive = Join-Path $runtimeDir "commandlinetools-win-14742923_latest.zip"
$gradleArchive = Join-Path $runtimeDir "gradle-8.11.1-bin.zip"

New-Item -ItemType Directory -Force -Path $toolRoot,$runtimeDir | Out-Null
if (-not $ProxyUrl -and (Test-NetConnection 127.0.0.1 -Port 7990 -InformationLevel Quiet)) {
    $ProxyUrl = "http://127.0.0.1:7990"
}

function Download-VerifiedFile([string]$url, [string]$destination, [string]$expectedChecksum) {
    $algorithm = if ($expectedChecksum.Length -eq 40) { "SHA1" } else { "SHA256" }
    if ($Force) {
        Remove-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $destination) {
        $existing = (Get-FileHash -LiteralPath $destination -Algorithm $algorithm).Hash.ToLowerInvariant()
        if ($existing -eq $expectedChecksum.ToLowerInvariant()) { return }
    }
    $curlArguments = @("-L", "--fail", "--silent", "--show-error", "--retry", "8", "--retry-delay", "2", "--retry-all-errors", "--connect-timeout", "30", "--speed-limit", "1024", "--speed-time", "60", "--continue-at", "-", "--output", $destination)
    if ($ProxyUrl) { $curlArguments += @("--proxy", $ProxyUrl) }
    $curlArguments += $url
    & curl.exe @curlArguments
    if ($LASTEXITCODE -ne 0 -and $ProxyUrl) {
        Write-Warning "Proxy download failed; retrying directly: $url"
        $directArguments = @("-L", "--fail", "--silent", "--show-error", "--retry", "8", "--retry-delay", "2", "--retry-all-errors", "--continue-at", "-", "--output", $destination, $url)
        & curl.exe @directArguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed through proxy and direct connection for $url"
    }
    $actual = (Get-FileHash -LiteralPath $destination -Algorithm $algorithm).Hash.ToLowerInvariant()
    if ($actual -ne $expectedChecksum.ToLowerInvariant()) {
        throw "$algorithm checksum mismatch for $destination. Expected $expectedChecksum, got $actual"
    }
}

if ($Force -or -not (Test-Path -LiteralPath (Join-Path $jdkRoot "bin\java.exe"))) {
    $jdkUrl = "https://aka.ms/download-jdk/microsoft-jdk-21-windows-x64.zip"
    $checksumArguments = @("-L", "--fail", "--silent", "--show-error")
    if ($ProxyUrl) { $checksumArguments += @("--proxy", $ProxyUrl) }
    $checksumArguments += "${jdkUrl}.sha256sum.txt"
    $checksumText = (& curl.exe @checksumArguments) -join "`n"
    $jdkChecksum = ([regex]::Match($checksumText, "[a-fA-F0-9]{64}")).Value
    if (-not $jdkChecksum) { throw "Unable to read the Microsoft OpenJDK checksum" }
    Download-VerifiedFile $jdkUrl $jdkArchive $jdkChecksum
    $jdkExtract = Join-Path $runtimeDir "jdk-extract"
    Remove-Item -LiteralPath $jdkExtract -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $jdkArchive -DestinationPath $jdkExtract -Force
    $jdkSource = Get-ChildItem -LiteralPath $jdkExtract -Directory | Select-Object -First 1
    if (-not $jdkSource) { throw "Microsoft OpenJDK archive has no root directory" }
    Remove-Item -LiteralPath $jdkRoot -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $jdkSource.FullName -Destination $jdkRoot
    Remove-Item -LiteralPath $jdkExtract -Recurse -Force
}

$env:JAVA_HOME = $jdkRoot
$env:PATH = "$jdkRoot\bin;$env:PATH"

if ($Force -or -not (Test-Path -LiteralPath (Join-Path $sdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"))) {
    Download-VerifiedFile `
        "https://dl.google.com/android/repository/commandlinetools-win-14742923_latest.zip" `
        $sdkArchive `
        "16b3f45ddb3d85ea6bbe6a1c0b47146daf0db450"
    $sdkExtract = Join-Path $runtimeDir "sdk-extract"
    Remove-Item -LiteralPath $sdkExtract -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $sdkArchive -DestinationPath $sdkExtract -Force
    $latest = Join-Path $sdkRoot "cmdline-tools\latest"
    Remove-Item -LiteralPath $latest -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $latest) | Out-Null
    Move-Item -LiteralPath (Join-Path $sdkExtract "cmdline-tools") -Destination $latest
    Remove-Item -LiteralPath $sdkExtract -Recurse -Force
}

$sdkManager = Join-Path $sdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"
$sdkProxyArguments = @()
if ($ProxyUrl) {
    $proxyUri = [Uri]$ProxyUrl
    $sdkProxyArguments = @("--proxy=http", "--proxy_host=$($proxyUri.Host)", "--proxy_port=$($proxyUri.Port)")
}
$licenses = 1..20 | ForEach-Object { "y" }
$licenses | & $sdkManager --sdk_root=$sdkRoot @sdkProxyArguments --licenses | Out-Null
& $sdkManager --sdk_root=$sdkRoot @sdkProxyArguments "platform-tools" "platforms;android-35" "build-tools;35.0.0"
if ($LASTEXITCODE -ne 0) { throw "Android SDK package installation failed" }

if ($Force -or -not (Test-Path -LiteralPath (Join-Path $gradleRoot "bin\gradle.bat"))) {
    $gradleUrl = "https://services.gradle.org/distributions/gradle-8.11.1-bin.zip"
    $gradleChecksum = "f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6"
    Download-VerifiedFile $gradleUrl $gradleArchive $gradleChecksum
    Remove-Item -LiteralPath $gradleRoot -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $gradleArchive -DestinationPath $toolRoot -Force
}

$gradle = Join-Path $gradleRoot "bin\gradle.bat"
if ($ProxyUrl) {
    $proxyUri = [Uri]$ProxyUrl
    $env:GRADLE_OPTS = "-Dhttps.proxyHost=$($proxyUri.Host) -Dhttps.proxyPort=$($proxyUri.Port) -Dhttp.proxyHost=$($proxyUri.Host) -Dhttp.proxyPort=$($proxyUri.Port)"
}
& $gradle -p (Join-Path $root "android") wrapper --gradle-version 8.11.1 --distribution-type bin
if ($LASTEXITCODE -ne 0) { throw "Gradle wrapper generation failed" }

[System.IO.File]::WriteAllText(
    (Join-Path $root "android\local.properties"),
    "sdk.dir=$($sdkRoot.Replace('\', '\\'))`r`n",
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output "Android toolchain ready"
Write-Output "JAVA_HOME=$jdkRoot"
Write-Output "ANDROID_HOME=$sdkRoot"
