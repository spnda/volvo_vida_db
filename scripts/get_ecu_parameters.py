#!/usr/bin/env python3

from typing import Any, Generator
import sys
import pandas as pd
import duckdb

from read_csv import get_csv, DatabaseFile
from vin_decoder import decode_vin

get_csv(DatabaseFile.t100)
get_csv(DatabaseFile.t101)
get_csv(DatabaseFile.t102)
get_csv(DatabaseFile.t141)
get_csv(DatabaseFile.t144)
get_csv(DatabaseFile.t150)
get_csv(DatabaseFile.t155)
get_csv(DatabaseFile.t160)
get_csv(DatabaseFile.t161)
get_csv(DatabaseFile.t162)
get_csv(DatabaseFile.t191)

def get_ecu_identifiers(profile_identifier: str) -> pd.DataFrame:
    return duckdb.sql(f"""
                 SELECT p.title, e.identifier as EcuIdentifier, e.name as EcuName, ev.identifier as EcuVariantIdentifier, et.identifier as EcuTypeIdentifier
                 FROM t161 p
                 INNER JOIN t160 dev ON dev.fkT161_Profile = p.id
                 INNER JOIN t100 ev ON ev.id = dev.fkT100_EcuVariant
                 INNER JOIN t101 e ON e.id = ev.fkT101_Ecu
                 INNER JOIN t102 et on et.id = e.fkT102_EcuType
                 WHERE p.identifier = '{profile_identifier}'
                 ORDER BY e.identifier
    """).df()

def get_can_parameters(ecu_identifier: str) -> pd.DataFrame:
    # AND NOT td.data = '' AND NOT b.name = 'As usage only'
    return duckdb.sql(f"""
                 SELECT DISTINCT ev.id as EcuID, ev.identifier as EcuIdentifier, b.name as BlockName, b.offset, b.length, bvparent.CompareValue as HexValue, s.definition as Conversion, b.fkT190_Text as TextID, td.data as Text, td2.data as Unit
                 FROM t100 ev
                 INNER JOIN t144 bc ON ev.id = bc.fkT100_EcuVariant 
                 INNER JOIN t141 b ON bc.fkT141_Block_Child = b.id
                 INNER JOIN t150 bv on b.id = bv.fkT141_block 
                 INNER JOIN t141 bparent on bc.fkT141_Block_Parent = bparent.id
                 INNER JOIN t150 bvparent on bparent.id = bvparent.fkt141_block
                 INNER JOIN t155 s on s.id = bv.fkT155_Scaling
                 INNER JOIN t191 td on td.fkT190_Text = b.fkT190_Text AND td.fkT193_Language = 19
	             INNER JOIN t191 td2 on td2.fkT190_Text = bv.fkT190_Text_ppeUnit AND td2.fkT193_Language = 19
                 WHERE ev.identifier = '{ecu_identifier}' AND NOT bvparent.CompareValue = ''
                 ORDER BY td.data
    """).df()

def get_can_parameters_for_profiles(profile_identifiers: list[str]) -> Generator[tuple[str, str, pd.DataFrame], Any, None]:
    for profile in profile_identifiers:
        ecus = get_ecu_identifiers(profile)
        for _, row in ecus.iterrows():
            can_data = get_can_parameters(row['EcuVariantIdentifier'])
            yield (row['EcuVariantIdentifier'], row['EcuIdentifier'], can_data)

if __name__ == '__main__':
    # You can figure out the profiles manually through find_vehicle_profiles or using the VIN with vin_decoder.py
    profiles = []

    # If the profiles are empty, we expect a VIN to be passed for decoding.
    if len(profiles) == 0 and len(sys.argv) == 1:
        print("Usage: get_ecu_parameters.py <VIN>")
    else:
        if len(profiles) == 0:
            vehicle = decode_vin(sys.argv[1])
            profiles = vehicle.get_vehicle_profiles()
        
        for params in get_can_parameters_for_profiles(profiles):
            params[2].to_csv(f'ecu/{params[1]}_{params[0]}.csv', sep=',', encoding='utf-8', index=False)
            print(f'Written CAN data to CSV: {params[1]}_{params[0]}')
