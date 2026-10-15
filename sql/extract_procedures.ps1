. $PSScriptRoot\sql_server.ps1

$dbnames = 'basedata', 'carcom', 'DiagSwdlRepository', 'DiceTiming' # Edit if you want any other tables

$folder = "procedures"

foreach ($dbname in $dbnames) {
    Write-Output "Writing procedures for '$dbname'..."

    try {
        $modules = Invoke-Sqlcmd @parameters -Database $dbname -MaxCharLength 1000000 -Query @"
        SELECT OBJECT_SCHEMA_NAME(m.object_id) AS SchemaName, o.name, o.type_desc, m.definition
        FROM sys.sql_modules m JOIN sys.objects o ON o.object_id = m.object_id
"@

        $dbfolder = "$folder\$dbname"
        if (-not (Test-Path $dbfolder -PathType Container)) {
            try {
                New-Item -Path $dbfolder -ItemType Directory -ErrorAction Stop
            } catch {
                Write-Error "Failed to create directory 'procedures'. $_"
                return
            }
        }

        foreach ($m in $modules) {
            if ($m.Definition -is [DBNull]) {
                # created WITH ENCRYPTION, no source available
                Write-Output "Skipping encrypted $($m.SchemaName).$($m.Name)."
                continue
            }
            Set-Content -Encoding UTF8 -Path "$dbfolder\$($m.SchemaName).$($m.Name).sql" -Value $m.Definition
        }
    } catch {
        Write-Error "Failed to export procedures from DB $dbname. $_"
        continue
    }
}
