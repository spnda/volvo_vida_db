# volvo_vida_db

This repository contains scripts to extract and work with data from the internal Volvo VIDA database.

Some of the SQL commands in the scripts I converted from [Tigo2000's repository](https://github.com/Tigo2000/Volvo-VIDA/).
A lot of the information and ideas als come from that repository.

The Python scripts use duckdb and pandas to work with the data.

### Extracting data from the database

Depending on wether PowerShell 7 and the SQLServer module are installed, you can either use `generate_csv.ps1` or `generate_csv.bat`.
The PowerShell script takes significantly longer than the Batch script does to generate, but is capable of outputting completely correct files.
The PowerShell script uses the `UseQuotes` option on `Export-Csv` which was introduced in PowerShell 7. On Windows 7 Professional the last working version of PowerShell 7 is 7.2.9.
The SQL credentials are already written into the scripts and won't need to be changed.

### Getting vehicle profiles

The `scripts/find_vehicle_profiles.py` script can assist filtering the T161_Profile table to find all profiles
for a specific vehicle. The script will ask things such as the vehicle model, year, engine, transmission, etc.
to filter the profiles. At the end, the script will print a list of all profiles that match the criteria.
Currently, the script can only work with the top 3 levels, as higher levels only contain certain variations and
combinations of the already specified data.

Another option is to use `scripts/vin_decoder.py`, which takes a VIN string and decodes it.
It will then print the relevant vehicle information including a list of all applicable vehicle profiles.

### Getting CAN parameters

Using `scripts/get_ecu_parameters.py` you can get a CSV file for every ECU in the car as specified by the vehicle profile(s).
The CSV file will contain all known CAN parameters, their localized name, their byte offset, and a conversion function.

### Processing data conversion functions

The conversion methods found in the outputted CSV file can be applied with the `scripts/evaluate_conversion.py` script.
It parses the expression into a simple executable AST that supports the feature set required for the expressions from the VIDA database.
