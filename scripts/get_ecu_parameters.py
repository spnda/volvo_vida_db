import os
import json
import pandas as pd
import duckdb
import inquirer

from read_csv import t100, t101, t102, t141, t144, t150, t155, t160, t161, t162, t191

def get_ecu_identifiers(profile_identifier) -> pd.DataFrame:
    return duckdb.query(f"""
                 SELECT p.title, e.identifier as EcuIdentifier, e.name as EcuName, ev.identifier as EcuVariantIdentifier, et.identifier as EcuTypeIdentifier
                 FROM t161 p
                 INNER JOIN t160 dev ON dev.fkt161_profile = p.id
                 INNER JOIN t100 ev ON ev.id = dev.fkt100_ecuvariant
                 INNER JOIN t101 e ON e.id = ev.fkt101_ecu
                 INNER JOIN t102 et on et.id = e.fkt102_ecutype
                 WHERE p.identifier = '{profile_identifier}'
                 ORDER BY e.identifier
    """).to_df()

def get_can_parameters(ecu_identifier) -> pd.DataFrame:
    # AND NOT td.data = '' AND NOT b.name = 'As usage only'
    return duckdb.query(f"""
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
    """).to_df()

# All the profile identifiers as determined with find_vehicle_profiles.py
# Change this to whatever that script outputs
model_identifiers = ['0b00c8af8020c059', '0b00c8af823216ee', '0b00c8af8247622b']

for id in model_identifiers:
    print(f"\nGetting ECU identifiers for profile {id}...")
    ecu_identifiers = get_ecu_identifiers(id)
    print(ecu_identifiers)

    if not os.path.exists('ecu'):
        os.mkdir('ecu')
    first_idx = 0
    for idx, row in ecu_identifiers.iterrows():
        if idx < first_idx:
            continue
        parameters = get_can_parameters(row['EcuVariantIdentifier'])
        parameters.to_csv(f'ecu/{row["EcuTypeIdentifier"]}_{row["EcuIdentifier"]}.csv', sep=',', encoding='utf-8', index=False)
        print(f"Finished writing parameters for {row['EcuIdentifier']}. {idx + 1}/{len(ecu_identifiers)} written.")
