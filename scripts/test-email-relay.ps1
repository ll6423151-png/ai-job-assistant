param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env.online"),
    [string]$PublicUrlPath = (Join-Path (Split-Path -Parent $PSScriptRoot) "runtime\email-relay-public-url.txt")
)

$ErrorActionPreference = "Stop"

function Read-Settings([string]$Path) {
    $settings = @{}
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match "^([A-Z0-9_]+)=(.*)$") {
            $settings[$matches[1]] = $matches[2].Trim()
        }
    }
    return $settings
}

function Invoke-Relay([string]$Uri, [string]$Token, [string]$Body) {
    $request = [System.Net.HttpWebRequest]::Create($Uri)
    $request.Method = "POST"
    $request.ContentType = "application/json"
    $request.Headers["Authorization"] = "Bearer $Token"
    $request.Timeout = 30000
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
    $request.ContentLength = $bytes.Length
    $stream = $request.GetRequestStream()
    try {
        $stream.Write($bytes, 0, $bytes.Length)
    } finally {
        $stream.Dispose()
    }
    try {
        $response = $request.GetResponse()
        try { return [int]$response.StatusCode } finally { $response.Dispose() }
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) {
            $response = $_.Exception.Response
            try { return [int]$response.StatusCode } finally { $response.Dispose() }
        }
        throw
    }
}

if (-not (Test-Path -LiteralPath $ConfigPath)) { throw "Missing private online configuration" }
if (-not (Test-Path -LiteralPath $PublicUrlPath)) { throw "Missing Quick Tunnel URL" }
$settings = Read-Settings $ConfigPath
if (-not $settings["SMTP_USERNAME"] -or -not $settings["EMAIL_RELAY_TOKEN"]) {
    throw "SMTP sender and email relay token are required"
}
$publicUrl = [System.IO.File]::ReadAllText($PublicUrlPath).Trim().TrimEnd("/")
$uri = "$publicUrl/api/internal/email-relay"
$payload = @{
    recipient = $settings["SMTP_USERNAME"]
    code = "654321"
    purpose = "login"
} | ConvertTo-Json -Compress

$wrongStatus = Invoke-Relay $uri "wrong-token" $payload
$validStatus = Invoke-Relay $uri $settings["EMAIL_RELAY_TOKEN"] $payload
if ($wrongStatus -ne 401) { throw "Wrong relay token returned HTTP $wrongStatus instead of 401" }
if ($validStatus -ne 204) { throw "Valid relay request failed with HTTP $validStatus" }

Write-Output "Email relay rejected an invalid token and accepted an authenticated QQ SMTP test."
