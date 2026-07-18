param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env.online")
)

$ErrorActionPreference = "Stop"

function New-SecureValue([int]$ByteCount, [string]$Prefix = "") {
    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    $encoded = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    return "$Prefix$encoded"
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    [System.IO.File]::WriteAllText($ConfigPath, "", (New-Object System.Text.UTF8Encoding($false)))
}

$lines = [System.Collections.Generic.List[string]]::new()
$values = @{}
foreach ($line in [System.IO.File]::ReadAllLines($ConfigPath)) {
    $lines.Add($line)
    if ($line -match "^\s*([A-Z0-9_]+)=(.*)$") {
        $values[$matches[1]] = $matches[2].Trim()
    }
}

$required = @{
    AUTH_SECRET_KEY = New-SecureValue 48
    BOOTSTRAP_ADMIN_PASSWORD = New-SecureValue 24 "Cp!"
    EMAIL_RELAY_TOKEN = New-SecureValue 48 "relay_"
}

$changed = @()
foreach ($key in $required.Keys) {
    $current = [string]$values[$key]
    $needsValue = -not $current
    if ($key -eq "AUTH_SECRET_KEY") { $needsValue = $current.Length -lt 32 }
    if ($key -eq "BOOTSTRAP_ADMIN_PASSWORD") { $needsValue = -not $current -or $current -eq "admin123" }
    if ($key -eq "EMAIL_RELAY_TOKEN") { $needsValue = $current.Length -lt 32 }
    if (-not $needsValue) { continue }

    $replacement = "$key=$($required[$key])"
    $index = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$key=") { $index = $i; break }
    }
    if ($index -ge 0) {
        $lines[$index] = $replacement
    } else {
        $lines.Add($replacement)
    }
    $changed += $key
}

if ($changed.Count -gt 0) {
    [System.IO.File]::WriteAllLines($ConfigPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
}

[pscustomobject]@{
    ConfigPath = $ConfigPath
    ChangedKeys = @($changed)
    Ready = $true
}
