# This file just contains SQL credentials & server information
# These are the credentials of the VIDA database put into a PSCredential object for use with Invoke-Sqlcmd
$password = 'GunnarS3g3' | ConvertTo-SecureString -AsPlainText -Force
$credentials = New-Object System.Management.Automation.PSCredential -ArgumentList 'sa', $password

$computerName = $env:COMPUTERNAME
$serverInstance = "$computerName\VIDA"  # Assuming the instance name is always "VIDA"

$parameters = @{
    ServerInstance = $serverInstance
    Credential = $credentials
    TrustServerCertificate = $true
}
