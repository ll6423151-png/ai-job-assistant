param([Parameter(Mandatory = $true)][string]$BaseUrl)
$ErrorActionPreference = "Stop"
$uri = [Uri]$BaseUrl
if ($uri.Scheme -ne "https" -or -not $uri.Host -or $uri.Host.EndsWith(".invalid")) {
    throw "BaseUrl must be the fixed HTTPS application URL"
}
Start-Process $uri.AbsoluteUri
