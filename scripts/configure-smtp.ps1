param(
    [string]$Sender
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root ".env.online"

$settings = [ordered]@{}
if (Test-Path -LiteralPath $configPath) {
    foreach ($line in [System.IO.File]::ReadAllLines($configPath)) {
        if (-not $line -or $line.TrimStart().StartsWith("#")) { continue }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) { $settings[$parts[0].Trim()] = $parts[1].Trim() }
    }
}

$sender = $(if ($Sender) { $Sender } else { Read-Host "System QQ sender email (example: 12345678@qq.com)" })
$sender = $sender.Trim().ToLowerInvariant()
if ($sender -notmatch '^[1-9][0-9]{4,11}@qq\.com$') {
    throw "A valid QQ email is required"
}

$secureCode = Read-Host "QQ SMTP authorization code (input is hidden)" -AsSecureString
$codePointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureCode)
try {
    $authorizationCode = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($codePointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($codePointer)
}
if ([string]::IsNullOrWhiteSpace($authorizationCode)) {
    throw "QQ SMTP authorization code is required"
}

$settings["SMTP_HOST"] = "smtp.qq.com"
$settings["SMTP_PORT"] = "465"
$settings["SMTP_USERNAME"] = $sender
$settings["SMTP_AUTHORIZATION_CODE"] = $authorizationCode.Trim()
$settings["SMTP_SENDER_NAME"] = "CareerPilot AI"
$settings["SMTP_USE_SSL"] = "true"

$lines = foreach ($entry in $settings.GetEnumerator()) {
    "{0}={1}" -f $entry.Key, $entry.Value
}
[System.IO.File]::WriteAllLines($configPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
$authorizationCode = $null

Write-Output "QQ SMTP configuration saved to the private local environment file."
Write-Output "The authorization code was not printed."
