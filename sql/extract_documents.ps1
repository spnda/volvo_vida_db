. $PSScriptRoot\sql_server.ps1

$folder = "documents"

New-Item -ItemType Directory -Path $folder -ErrorAction SilentlyContinue

$documents = Invoke-Sqlcmd @parameters -MaxBinaryLength 10000000 -Query @"
    SELECT * FROM [servicerep_en-US].dbo.Document
"@

foreach ($row in $documents) {
    $id = $row.id
    Write-Output "Writing document '$id'..."

    $zip_file = "$PWD\$folder\$id.zip"
    [System.IO.File]::WriteAllBytes($zip_file, $row.XmlContent)

    Expand-Archive -Path $zip_file -DestinationPath "$PWD\$folder" -Force

    # The path variable in the table includes both the filename and the folder,
    # but within the zip the file is only named by the filename.
    $name = Split-Path $row.path -Leaf
    $xml_file = "$folder/$name"
    $dest = "$folder/$($row.path)"

    $vcc_path = "$folder/$($row.vccNumber)"
    if(-not (Test-Path $vcc_path)) {
        New-Item -Path $vcc_path -ItemType Directory -Force | Out-Null
    }
    Move-Item -Path $xml_file -Destination $dest -Force

    Remove-Item -Path $zip_file
}
