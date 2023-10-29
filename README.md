# volvo_vida_db

This repository contains scripts to extract and work with data from the internal Volvo VIDA database.

The generate_csv.bat script uses SQL Server to create CSV tables, to avoid having to work with SQL Server directly.
I'm still looking to get PowerShell running on my Win7 VM so I can use `Invoke-Sqlcmd` and `Export-Csv` to get a cleaner and more correct output.

Some of the SQL commands in the scripts I converted from [Tigo2000's repository](https://github.com/Tigo2000/Volvo-VIDA/).
A lot of the information and ideas als come from that repository.

The Python scripts use pandas and duckdb (pandasql was extremely slow) to work with the data.

## Getting vehicle profiles

The `scripts/find_vehicle_profiles.py` script can assist filtering the T161_Profile table to find all profiles
for a specific vehicle. The script will ask things such as the vehicle model, year, engine, transmission, etc.
to filter the profiles. At the end, the script will print a list of all profiles that match the criteria.
Currently, the script can only work with the top 3 levels, as higher levels only contain certain variations and
combinations of the already specified data.

Using `scripts/get_ecu_parameters.py` you can get a CSV file for every ECU in the car as specified by the vehicle profile(s).
The CSV file will contain all known CAN parameters, their localized name, their byte offset, and a conversion function.

The conversion methods found in the outputted CSV file can be applied with the `scripts/evaluate_conversion.py` script.
It parses the expression with Python's built-in AST and only supports a limited feature set that is sufficient for the expressions found in the VIDA database. 
