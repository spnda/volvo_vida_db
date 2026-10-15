. $PSScriptRoot\sql_server.ps1

$dbnames = 'basedata', 'carcom', 'DiagSwdlRepository', 'DiceTiming' # Edit if you want any other tables

foreach ($dbname in $dbnames) {
    if ($dbname -eq 'imagerepository') {
        # the imagerepository table contains binary data. there's a separate script for extracting the images.
        Write-Output "Skipping imagerepository database."
        continue
    }

    # Construct SQL query to get table names from the database
    $query = @"
        SELECT TABLE_NAME
        FROM $($dbname).INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE';
"@

    # Get the list of tables from the database
    try {
        $db_tables = Invoke-Sqlcmd @parameters -Database $dbname -Query $query -ErrorAction Stop
    } catch {
        Write-Error "Failed to retrieve tables from database '$dbname'. $_"
        continue
    }

    # Create directory for CSV files if it doesn't exist
    $folder = "csv/$dbname/"
    if (-not (Test-Path $folder -PathType Container)) {
        try {
            New-Item -Path $folder -ItemType Directory -ErrorAction Stop
        } catch {
            Write-Error "Failed to create directory '$folder'. $_"
            continue
        }
    }

    # Loop through each table and export its data to a CSV file
    foreach ($table_row in $db_tables) {
        $table = $table_row.TABLE_NAME
        $file_path = Join-Path -Path $folder -ChildPath "$table.csv"

        if ($table -eq 'T111_Service') {
            # T111_Service contains binary data. extract_services.ps1 writes its CSV and extracts the definitions.
            Write-Output "Skipping T111_Service table."
            continue
        }
        if ($dbname -eq 'DiagSwdlRepository' -and $table_row.TABLE_NAME.StartsWith('Script')) {
            # Script extraction is handled by extract_scripts.ps1
            Write-Output "Skipping $($table_row.TABLE_NAME) table."
            continue
        }

        # Check if CSV file already exists, if yes, skip exporting
        if (Test-Path $file_path -PathType Leaf) {
            Write-Output "CSV file for table '$table' already exists. Skipping export."
            continue
        }

        # Construct SQL query to select all data from the table
        $query = @"
            SELECT * FROM $($dbname).dbo.$table;
"@

        # Execute SQL query and export data to CSV file
        try {
            Write-Output "Exporting data from table '$table' to CSV file..."
            $rows = Invoke-Sqlcmd @parameters -Database $dbname -Query $query -ErrorAction Stop
            $rows | Export-Csv -Encoding UTF8 -UseQuotes AsNeeded -NoTypeInformation -path $file_path
        } catch {
            Write-Error "Failed to export data from table '$table'. $_"
            continue
        }
    }
}
