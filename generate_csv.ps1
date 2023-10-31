# These are the credentials of the VIDA database put into a PSCredential object for use with Invoke-Sqlcmd
$password = 'GunnarS3g3' | ConvertTo-SecureString -AsPlainText -Force
$credentials = New-Object System.Management.Automation.PSCredential -ArgumentList 'sa', $password

$parameters = @{
    ServerInstance = 'WIN-JR1TF78ROOI\VIDA'
    Credential = $credentials
    TrustServerCertificate = $true
}

$dbnames = 'basedata','carcom','imagerepository' # Edit if you want any other tables
foreach ($dbname in $dbnames) {
    # Get a list of all tables in the given databases
    $db_tables = Invoke-Sqlcmd @parameters -Query @"
        SELECT TABLE_NAME
        FROM $($dbname).INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE';
"@

    # Make sure the target directory exists 
    $folder = 'csv/' + $dbname + '/'
    if (!(Test-Path -PathType container $folder))
    {
        New-Item -ItemType Directory -Path $folder | Out-Null
    }

    # Write the contents of each table as CSVs
    # TODO: This script takes VERY long to execute. Use threading?
    foreach ($table_row in $db_tables) {
        $table = $table_row.Item(0)
        $file_path = $($folder + $table + '.csv')
        Write-Output $table
        if (Test-Path $file_path -PathType Leaf) {
            continue
        }

        $rows = Invoke-Sqlcmd @parameters -Query @"
            set nocount on;
            SELECT * FROM $($dbname).dbo.$($table)
"@
        $rows | Export-Csv -Encoding UTF8 -UseQuotes AsNeeded -NoTypeInformation -path $file_path
        Write-Output "Written $table"
    }
}

