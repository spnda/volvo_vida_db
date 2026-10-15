. $PSScriptRoot\sql_server.ps1

$graphics = Invoke-Sqlcmd @parameters -MaxBinaryLength 10000000 -Query @"
    SELECT * FROM imagerepository.dbo.LocalizedGraphics
"@

New-Item -ItemType Directory -Path 'extracted_images' | Out-Null
foreach ($row in $graphics) {
    Write-Output "Writing image '$($row.fkGraphic)'..."

    $file = "$PWD\extracted_images\$($row.path)"
    [System.IO.File]::WriteAllBytes($file, $row.imageData)
}
