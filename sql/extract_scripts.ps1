. $PSScriptRoot\sql_server.ps1

New-Item -ItemType Directory -Path 'csv/DiagSwdlRepository/' -ErrorAction SilentlyContinue

# First, extract metadata into CSV files
$db_tables = 'Script','ScriptCarFunction','ScriptProfileMap','ScriptType','ScriptVariant'
foreach ($table in $db_tables) {
    Write-Output "Writing CSV '$($table)'..."
    $file_path = 'csv/DiagSwdlRepository/' + $table + '.csv'
    $rows = Invoke-Sqlcmd @parameters -Query @"
        set nocount on;
        SELECT * FROM DiagSwdlRepository.dbo.$($table)
"@
    $rows | Export-Csv -Encoding UTF8 -UseQuotes AsNeeded -NoTypeInformation -path $file_path
}

# Now, extract the ScriptContent table but write the binary data into separate files
$target_language = 15 # This is en-US. For values, check DiagSwdlRepository.dbo.Language
$rows = Invoke-Sqlcmd @parameters -MaxBinaryLength 10000000 -Query @"
    SELECT * FROM DiagSwdlRepository.dbo.ScriptContent
    WHERE fkLanguage=$($target_language)
"@

$rows | Export-Csv -Encoding UTF8 -UseQuotes AsNeeded -NoTypeInformation -path 'csv/DiagSwdlRepository/ScriptContent.csv'

# The methodology of extracting the scripts I found here: http://www.stevediraddo.com/2019/01/13/volvo-canbus-tinkering/
New-Item -ItemType Directory -Path 'extracted_scripts/' -ErrorAction SilentlyContinue
foreach ($row in $rows) {
    Write-Output "Writing script '$($row.fkScript)'..."

    # Write the zip file data to a file
    # TODO: Using MemoryStream and ZipArchive, it should be possible to do this in memory with .NET
    $zip_file = "$PWD\extracted_scripts\$($row.fkScript).zip"
    [System.IO.File]::WriteAllBytes($zip_file, $row.XmlDataCompressed)
    
    # Extract the script XML from the archive, and give it an xml ending
    Expand-Archive -Path $zip_file -DestinationPath "$PWD\extracted_scripts"
    Rename-Item -Path "$PWD\extracted_scripts\$($row.fkScript)" -NewName "$PWD\extracted_scripts\$($row.fkScript).xml"
    Remove-Item -Path $zip_file
}
