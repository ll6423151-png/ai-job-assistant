param(
    [Parameter(Mandatory = $true)][string]$ServerHost,
    [string]$SshUser = "ubuntu",
    [Parameter(Mandatory = $true)][string]$Domain,
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\id_rsa"
)

$ErrorActionPreference = "Stop"
$ssh = Get-Command ssh.exe -ErrorAction Stop
if (-not (Test-Path -LiteralPath $SshKeyPath)) { throw "SSH key not found: $SshKeyPath" }
if ($Domain -notmatch '^[A-Za-z0-9.-]+$') { throw "Domain is invalid" }
if ($ServerHost -notmatch '^[A-Za-z0-9.:-]+$') { throw "ServerHost is invalid" }
if ($SshUser -notmatch '^[A-Za-z0-9_-]+$') { throw "SshUser is invalid" }

$remote = "$SshUser@$ServerHost"
& $ssh.Source -i $SshKeyPath $remote "export CAREERPILOT_DOMAIN='$Domain'; bash /opt/careerpilot/deploy/oracle/update.sh"
if ($LASTEXITCODE -ne 0) { throw "Oracle update failed" }
