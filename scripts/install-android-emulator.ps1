param(
    [string]$ProxyUrl = $env:OUTBOUND_HTTPS_PROXY,
    [int]$ParallelDownloads = 4,
    [string]$AvdName = "CareerPilot_API35"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$toolRoot = Join-Path $root "tools\android-build"
$sdkRoot = Join-Path $toolRoot "android-sdk"
$jdkRoot = Join-Path $toolRoot "jdk"
$runtimeDir = Join-Path $root "runtime\android-emulator"
$avdRoot = Join-Path $toolRoot "avd"

if (-not (Test-Path -LiteralPath (Join-Path $sdkRoot "cmdline-tools\latest\bin\avdmanager.bat"))) {
    throw "Android command-line tools are missing. Run install-android-toolchain.ps1 first."
}
if (-not $ProxyUrl -and (Test-NetConnection 127.0.0.1 -Port 7990 -InformationLevel Quiet)) {
    $ProxyUrl = "http://127.0.0.1:7990"
}

New-Item -ItemType Directory -Force -Path $runtimeDir,$avdRoot | Out-Null

function Download-ChunkedVerifiedFile(
    [string]$Url,
    [string]$Destination,
    [long]$ExpectedSize,
    [string]$ExpectedSha1
) {
    if (Test-Path -LiteralPath $Destination) {
        $existing = Get-Item -LiteralPath $Destination
        if ($existing.Length -eq $ExpectedSize) {
            $existingHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA1).Hash.ToLowerInvariant()
            if ($existingHash -eq $ExpectedSha1.ToLowerInvariant()) { return }
        }
    }

    $chunkSize = 1MB
    $chunkCount = [math]::Ceiling($ExpectedSize / $chunkSize)
    $partDir = "$Destination.parts"
    Remove-Item -LiteralPath $partDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $partDir | Out-Null

    for ($batch = 0; $batch -lt $chunkCount; $batch += $ParallelDownloads) {
        $processes = @()
        for ($index = $batch; $index -lt [math]::Min($batch + $ParallelDownloads, $chunkCount); $index++) {
            $start = $index * $chunkSize
            $end = [math]::Min($ExpectedSize - 1, $start + $chunkSize - 1)
            $part = Join-Path $partDir ("part-{0:D4}.bin" -f $index)
            $arguments = @(
                "-L", "--fail", "--silent", "--show-error",
                "--retry", "8", "--retry-delay", "2", "--retry-all-errors",
                "--connect-timeout", "30", "--range", "$start-$end",
                "--output", $part
            )
            if ($ProxyUrl) { $arguments += @("--proxy", $ProxyUrl) }
            $arguments += $Url
            $processes += Start-Process -FilePath "curl.exe" -ArgumentList $arguments -NoNewWindow -PassThru
        }
        $processes | Wait-Process
        if ($processes | Where-Object { $_.ExitCode -ne 0 }) {
            throw "A download chunk failed for $Url"
        }
    }

    $stream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::Create)
    try {
        Get-ChildItem -LiteralPath $partDir -Filter "part-*.bin" |
            Sort-Object Name |
            ForEach-Object {
                $input = [System.IO.File]::OpenRead($_.FullName)
                try { $input.CopyTo($stream) } finally { $input.Dispose() }
            }
    } finally {
        $stream.Dispose()
    }

    $download = Get-Item -LiteralPath $Destination
    if ($download.Length -ne $ExpectedSize) {
        throw "Size mismatch for $Destination. Expected $ExpectedSize, got $($download.Length)."
    }
    $actualSha1 = (Get-FileHash -LiteralPath $Destination -Algorithm SHA1).Hash.ToLowerInvariant()
    if ($actualSha1 -ne $ExpectedSha1.ToLowerInvariant()) {
        throw "SHA1 mismatch for $Destination. Expected $ExpectedSha1, got $actualSha1."
    }
    Remove-Item -LiteralPath $partDir -Recurse -Force
}

$emulatorArchive = Join-Path $runtimeDir "emulator-windows_x64-15828024.zip"
$imageArchive = Join-Path $runtimeDir "x86_64-35_r02.zip"

Download-ChunkedVerifiedFile `
    "https://googledownloads.cn/android/repository/emulator-windows_x64-15828024.zip" `
    $emulatorArchive `
    453211385 `
    "ca808899920a1d2e4d0fce81d1d42968da67e486"

Download-ChunkedVerifiedFile `
    "https://googledownloads.cn/android/repository/sys-img/android/x86_64-35_r02.zip" `
    $imageArchive `
    782404023 `
    "2d857d170c0d1b827149565da34b3383e5306f7f"

$emulatorDir = Join-Path $sdkRoot "emulator"
if (-not (Test-Path -LiteralPath (Join-Path $emulatorDir "emulator.exe"))) {
    $extract = Join-Path $runtimeDir "emulator-extract"
    Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $emulatorArchive -DestinationPath $extract -Force
    $source = Get-ChildItem -LiteralPath $extract -Filter "emulator.exe" -Recurse -File | Select-Object -First 1
    if (-not $source) { throw "The emulator archive does not contain emulator.exe" }
    Remove-Item -LiteralPath $emulatorDir -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $source.Directory.FullName -Destination $emulatorDir
    Remove-Item -LiteralPath $extract -Recurse -Force
}

$emulatorPackageXml = Join-Path $emulatorDir "package.xml"
if (-not (Test-Path -LiteralPath $emulatorPackageXml)) {
    $packageDocument = New-Object System.Xml.XmlDocument
    $packageDocument.PreserveWhitespace = $true
    $packageDocument.LoadXml('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns2:repository xmlns:ns2="http://schemas.android.com/repository/android/common/02" xmlns:ns5="http://schemas.android.com/repository/android/generic/02"><license id="android-sdk-license" type="text"/><localPackage path="emulator" obsolete="false"><type-details xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns5:genericDetailsType"/><revision><major>37</major><minor>1</minor><micro>8</micro></revision><display-name>Android Emulator</display-name><uses-license ref="android-sdk-license"/></localPackage></ns2:repository>')
    $xmlSettings = New-Object System.Xml.XmlWriterSettings
    $xmlSettings.Encoding = New-Object System.Text.UTF8Encoding($false)
    $xmlSettings.Indent = $false
    $writer = [System.Xml.XmlWriter]::Create($emulatorPackageXml, $xmlSettings)
    try { $packageDocument.Save($writer) } finally { $writer.Dispose() }
}

$imageDir = Join-Path $sdkRoot "system-images\android-35\default\x86_64"
if (-not (Test-Path -LiteralPath (Join-Path $imageDir "system.img"))) {
    $extract = Join-Path $runtimeDir "image-extract"
    Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $imageArchive -DestinationPath $extract -Force
    $source = Get-ChildItem -LiteralPath $extract -Filter "system.img" -Recurse -File | Select-Object -First 1
    if (-not $source) { throw "The system image archive does not contain system.img" }
    Remove-Item -LiteralPath $imageDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $imageDir) | Out-Null
    Move-Item -LiteralPath $source.Directory.FullName -Destination $imageDir
    Remove-Item -LiteralPath $extract -Recurse -Force
}

$env:JAVA_HOME = $jdkRoot
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:ANDROID_AVD_HOME = $avdRoot
$env:PATH = "$jdkRoot\bin;$sdkRoot\emulator;$sdkRoot\platform-tools;$env:PATH"

$avdManager = Join-Path $sdkRoot "cmdline-tools\latest\bin\avdmanager.bat"
if (-not (Test-Path -LiteralPath (Join-Path $avdRoot "$AvdName.avd\config.ini"))) {
    "no" | & $avdManager create avd --force --name $AvdName --package "system-images;android-35;default;x86_64" --device "pixel_4"
    if ($LASTEXITCODE -ne 0) { throw "AVD creation failed" }
}

& (Join-Path $emulatorDir "emulator-check.exe") accel
Write-Output "Android emulator ready"
Write-Output "AVD=$AvdName"
Write-Output "ANDROID_AVD_HOME=$avdRoot"
