. $PSScriptRoot\sql_server.ps1

New-Item -ItemType Directory -Path 'csv/carcom/' -ErrorAction SilentlyContinue

# First, extract the service metadata into a CSV file, without the binary definition column
Write-Output "Writing CSV 'T111_Service'..."
$rows = Invoke-Sqlcmd @parameters -Query @"
    set nocount on;
    SELECT id, fkT122_Protocol, service, mode, serviceName, modeName, description, type, status, fkt130_Init_Timing_Service_Default
    FROM carcom.dbo.T111_Service
"@
$rows | Export-Csv -Encoding UTF8 -UseQuotes AsNeeded -NoTypeInformation -path 'csv/carcom/T111_Service.csv'

# Now, write each definition into its own XML file. The definition is the UTF-8 encoded content of a <service> element,
# which VIDA wraps the same way in Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Data.SPService.GetService.
$rows = Invoke-Sqlcmd @parameters -MaxBinaryLength 10000000 -Query @"
    SELECT id, definition FROM carcom.dbo.T111_Service
    WHERE definition IS NOT NULL
"@

New-Item -ItemType Directory -Path 'extracted_services/' -ErrorAction SilentlyContinue
$utf8 = [System.Text.Encoding]::UTF8
foreach ($row in $rows) {
    Write-Output "Writing service '$($row.id)'..."
    $header = $utf8.GetBytes("<?xml version=`"1.0`" encoding=`"utf-8`" ?><service id=`"$($row.id)`">")
    $footer = $utf8.GetBytes("</service>")
    [System.IO.File]::WriteAllBytes("$PWD\extracted_services\$($row.id).xml", $header + $row.definition + $footer)
}
