. $PSScriptRoot\sql_server.ps1

$dbnames = 'basedata','carcom' # Edit if you want any other tables
foreach ($dbname in $dbnames) {
    if ($dbname -eq 'imagerepository') {
        # the imagerepository table contains binary data. there's a separate script for extracting the images.
        continue
    }

    # Get a list of all tables in the given databases
    $db_tables = Invoke-Sqlcmd @parameters -Query @"
        SELECT TABLE_NAME
        FROM $($dbname).INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE';
"@

    # Make sure the target directory exists 
    $folder = 'csv/' + $dbname + '/'
    New-Item -ItemType Directory -Path $folder -ErrorAction SilentlyContinue

    # Write the contents of each table as CSVs
    # TODO: This script takes VERY long to execute. Use threading?
    foreach ($table_row in $db_tables) {
        $table = $table_row.Item(0)
        $file_path = $($folder + $table + '.csv')
        Write-Output $table

        # If the output is broken just comment out these next lines
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
