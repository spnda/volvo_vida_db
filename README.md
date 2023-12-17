# volvo_vida_db

This repository contains scripts to extract and work with data from the internal Volvo VIDA database.

Some SQL statements are based on procedures found in the VIDA SQL Server database and from scripts in [Tigo2000's repository](https://github.com/Tigo2000/Volvo-VIDA/).

The Python scripts use duckdb and pandas to work with the data.

### Extracting data from the database

Depending on wether PowerShell 7 and the SQLServer module are installed, you can either use `generate_csv.ps1` or `generate_csv.bat`.
The PowerShell scripts can take longer than the Batch script does to generate, but is capable of outputting completely correct files.
The PowerShell script uses the `UseQuotes` option on `Export-Csv` which was introduced in PowerShell 7. On Windows 7 Professional the last working version of PowerShell 7 is 7.2.9.
The SQL credentials are already written into the scripts and won't need to be changed.

### Getting vehicle profiles

Using `scripts/vin_decoder.py` you can get a list of VIDA vehicle profiles, as well as basic information about
the car such as model, year, engine, ...
The vehicle profiles are linked to various information in the database, such as a list of ECUs present in the vehicle.
A single vehicle is made up of multiple profiles for every combination of model, model year, engine, transmission, ...
The profile that represents a generic V50 for example will only link to data that is present in *every* V50.
Other profiles will then be more specific about things such as the engine, which will then link to the ECUs which are only present for that engine.
These profiles will become very important for the rest of the scripts.

### Getting CAN parameters

Using `scripts/write_ecu_data.py` you can get a CSV file for each ECU for the given vehicle VIN.
This will write a configs.csv file which contains information about how to interact with each ECU and through which physical bus.
It will also write a CSV for each ECU containing information how to ask for specific data and how to interpret the bits.

### Processing data conversion functions

The conversion methods found in the outputted CSV file can be applied with the `scripts/evaluate_conversion.py` script.
It parses the expression into a simple executable AST that supports the feature set required for the expressions from the VIDA database.

### Extracting scripts

The VIDA database contains XML-based scripts that can read and write data from and to the car.
These use the CAN protocol and are used to perform certain actions, but can also be used to figure out how the protocol works.
Reading these scripts can allow us to figure out how the CAN-based protocol works and how we can make use of it. 

The `sql/extract_scripts.ps1` can be used to extract all script metadata into CSV files and the actual scripts into decompressed XML files.
