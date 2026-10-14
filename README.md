# volvo_vida_db

This repository contains scripts to extract and work with data from the internal Volvo VIDA 2014D database.

Some SQL statements are based on procedures found in the VIDA SQL Server database and from scripts in [Tigo2000's repository](https://github.com/Tigo2000/Volvo-VIDA/).

The Python scripts use duckdb and pandas to work with the data.

## Getting the data

#### Extracting data from the database

Depending on wether PowerShell 7 and the SQLServer module are installed, you can either use `generate_csv.ps1` or `generate_csv.bat`.
The PowerShell scripts can take longer than the Batch script does to generate, but is capable of outputting completely correct files.
The PowerShell script uses the `UseQuotes` option on `Export-Csv` which was introduced in PowerShell 7. On Windows 7 Professional the last working version of PowerShell 7 is 7.2.9.
The SQL credentials are already written into the scripts and won't need to be changed.

#### Acquiring the .NET DICE interface services

VIDA needs to communicate with the DICE adapter through a service, which is apparently called "VidaEar" and is located in `VIDA/jboss/standalone/deployments/VidaEar.ear/VidaWeb.war/Diagnostics`. That folder contains quite a few DLLs which when inspected with a .NET decompiler like dotPeek reveal that they have not been stripped from debug information and actually still contain their NUnit unit tests! The same goes for all the Java applications found within VIDA I have looked at so far. The `BizServices` implement the VIDA scripting service (the thing that executes XML scripts) and all of the services that read data from the SQL database.

Using these applications/services it was fairly easy to reproduce the behavior and have actual test data to test our own implementation against. It also drastically helped to narrow down how VIDA/DICE actually communicate with the car and what all of the data in the SQL database means and how we can use it.

## Running the scripts

### Getting vehicle profiles

Using `scripts/vin_decoder.py` you can get a list of VIDA vehicle profiles, as well as basic information about
the car such as model, year, engine, ...
The vehicle profiles are linked to various information in the database, such as a list of ECUs present in the vehicle.
A single vehicle is made up of multiple profiles for every combination of model, model year, engine, transmission, ...
The profile that represents a generic V50 for example will only link to data that is present in *every* V50.
Other profiles will then be more specific about things such as the engine, which will then link to the ECUs which are only present for that engine.
These profiles will become very important for the rest of the scripts.

### Getting CAN parameters

Using `scripts/carcom.py export <VIN>` you can get a CSV file for each ECU of the vehicle in the `ecu` folder.
`ecus.csv` contains information about how to interact with each ECU and through which physical bus.
The CSV of each ECU lists its identifiers and how to interpret the bits of each parameter, including the texts of its states.

### Processing data conversion functions

The conversion methods found in the outputted CSV file can be applied with the `scripts/evaluate_conversion.py` script.
It parses the expression into a simple executable AST that supports the feature set required for the expressions from the VIDA database.

### Extracting scripts

The VIDA database contains XML-based scripts that can read and write data from and to the car.
These use the CAN protocol and are used to perform certain actions, but can also be used to figure out how the protocol works.
Reading these scripts can allow us to figure out how the CAN-based protocol works and how we can make use of it. 

The `sql/extract_scripts.ps1` can be used to extract all script metadata into CSV files and the actual scripts into decompressed XML files.
Similarly, `sql/extract_services.ps1` writes the diagnostic services (`carcom.T111_Service`) into a CSV file and the
service definitions into XML files in `extracted_services/`.

### carcom.py and d2.py

VIDA describes every ECU in its `carcom` database: how to reach it, which identifiers it can be asked for, and which
bits of each answer mean what. It talks to P1/P2-era ECUs (V50, S60, ...) with Volvo's own D2 protocol over CAN.
These two scripts reimplement both halves, so you can ask an ECU for a value and understand the answer without VIDA:

- `scripts/carcom.py` reads the ECU and identifier definitions. It is a port of
  `Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Blocks.BlockHandler`, so the results match what VIDA shows.
- `scripts/d2.py` builds D2 request frames, joins multi-frame answers back together and decodes them with the
  definitions from `carcom.py`. It came from `Vcc.Vida.DiagSwdl.VehCom2` (framing) and
  `Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.ResponseHandler` (decoding).

```
python volvo_vida_db/scripts/carcom.py ecus <VIN>                        # ECUs with address, bus and protocol
python volvo_vida_db/scripts/carcom.py params "30728979 AA" --csv cem.csv  # identifiers and parameters of a CEM
python volvo_vida_db/scripts/carcom.py dtcs "30684976  A"                # DTCs of an ECM
python volvo_vida_db/scripts/carcom.py text "wheel speed"                # search all texts
python volvo_vida_db/scripts/carcom.py types                             # all ECU types (also: addresses)
python volvo_vida_db/scripts/d2.py 50 REID 1A04                          # frame to read 0x1A04 from the CEM (0x50)
```

Requests are sent on the 29-bit CAN ID `0x000FFFFE` as `<format byte> <ECU address> <service> <data>`, for example
`CD 50 A6 1A 04 01 00 00`. VIDA does not know which CAN IDs the ECUs answer on: it accepts any odd 29-bit ID and takes
the ECU address from the second byte. The docstring of `d2.py` describes the framing.

Every identifier and value in the database has two sets of texts, units and scalings, which VIDA calls As and Ppe.
As are the translated texts a technician sees (`30-supply`, unit `Volt`), Ppe the engineering names (`VBat_A_Sense`,
unit `V`). VIDA shows As by default and falls back to Ppe where As is missing; `carcom.EcuBlocks` does the same and
can be switched to Ppe with `mode='ppe'`. The two sets do not always agree, see the docstring of `carcom.py`.
