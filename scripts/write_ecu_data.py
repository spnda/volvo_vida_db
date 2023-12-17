#!/usr/bin/env python3

from typing import Any, Generator
import sys
import pandas as pd

from read_csv import get_csvs, DatabaseFile, root_directory
from vin_decoder import decode_vin
from ecus import get_ecu_identifiers, get_can_parameters, get_ecu_config

def get_can_parameters_for_profiles(profile_identifiers: list[str]) -> Generator[tuple[str, str, pd.DataFrame], Any, None]:
    for profile in profile_identifiers:
        ecus = get_ecu_identifiers(profile).df()
        for _, row in ecus.iterrows():
            can_data = get_can_parameters(row['EcuVariantIdentifier']).df()
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

        ecu_configs: list[pd.DataFrame] = []
        for profile in profiles:
            ecu_ids = get_ecu_identifiers(profile).df()
            for _, row in ecu_ids.iterrows():
                config = get_ecu_config(row['EcuVariantIdentifier']).df()
                ecu_configs.append(config)

        configs = pd.concat(ecu_configs, axis=0)
        print('Writing CAN config for ECUs...')
        configs.to_csv(f'{root_directory}/ecu/configs.csv', sep=',', encoding='utf-8')
        
        for params in get_can_parameters_for_profiles(profiles):
            print(f'Writing CAN data for ECU {params[0]} of type {params[1]} to CSV...')
            params[2].to_csv(f'{root_directory}/ecu/{params[1]}_{params[0]}.csv', sep=',', encoding='utf-8', index=False)
