param(
    [Parameter(Mandatory = $true)][string]$ServerHost,
    [string]$SshUser = "ubuntu",
    [Parameter(Mandatory = $true)][string]$Domain,
    [Parameter(Mandatory = $true)][string]$CertificateEmail,
    [Parameter(Mandatory = $true)][string]$RepositoryUrl,
    [Parameter(Mandatory = $true)][string]$AdminPassword,
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\careerpilot_oracle",
    [string]$PostgresPassword,
    [string]$AuthSecret
)

$ErrorActionPreference = "Stop"
$arguments = @{
    ServerHost = $ServerHost
    SshUser = $SshUser
    Domain = $Domain
    CertificateEmail = $CertificateEmail
    RepositoryUrl = $RepositoryUrl
    AdminPassword = $AdminPassword
    SshKeyPath = $SshKeyPath
}
if ($PostgresPassword) { $arguments.PostgresPassword = $PostgresPassword }
if ($AuthSecret) { $arguments.AuthSecret = $AuthSecret }
& (Join-Path $PSScriptRoot "deploy-oracle.ps1") @arguments
if ($LASTEXITCODE -ne 0) { throw "Tencent Cloud deployment failed" }
