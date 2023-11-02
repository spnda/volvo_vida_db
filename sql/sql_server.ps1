# This file just contains SQL credentials & server information
# These are the credentials of the VIDA database put into a PSCredential object for use with Invoke-Sqlcmd
$password = 'GunnarS3g3' | ConvertTo-SecureString -AsPlainText -Force
$credentials = New-Object System.Management.Automation.PSCredential -ArgumentList 'sa', $password

$parameters = @{
    ServerInstance = 'WIN-JR1TF78ROOI\VIDA'
    Credential = $credentials
    TrustServerCertificate = $true
}
