#!/usr/bin/env python3

import math
import sys
import duckdb
import pandas
from read_csv import get_csv, DatabaseFile

# Simple wrapper around a single model row
class Model:
    def __init__(self, row: pandas.Series):
        self.vehicle_model = row['fkVehicleModel']
        self.model_year = row['fkModelYear']
        self.partner_group = row['fkPartnerGroup']

        # We reuse Model for comparing the rows from VINDecodeVariant, which does not include a fkBodyStyle
        # entry.
        self.body_style = row['fkBodyStyle'] if 'fkBodyStyle' in row and not math.isnan(row['fkBodyStyle']) else None

    def __eq__(self, other):
        return (isinstance(other, Model) and
                self.vehicle_model == other.vehicle_model and
                self.model_year == other.model_year and
                self.body_style == other.body_style and
                self.partner_group == other.partner_group)

    def __repr__(self):
        return f'<Model vehicle_model:{self.vehicle_model} model_year:{self.model_year} body_style:{self.body_style} partner_group:{self.partner_group}>'

# Represents a decoded vehicle from a VIN
class Vehicle:
    def __init__(self, model: Model, engine: int, transmission: int):
        self.vehicle_model = model.vehicle_model
        self.model_year = model.model_year
        self.partner_group = model.partner_group
        self.engine = engine
        self.transmission = transmission

    def get_vehicle_profiles(self) -> list[str]:
        """
        Gets the list of all vehicle profiles applicable for this Vehicle
        """
        get_csv(DatabaseFile.vehicle_profile)
        profiles = duckdb.sql(f"""
            SELECT DISTINCT * FROM vehicle_profile
            WHERE fkVehicleModel={self.vehicle_model} AND
            (fkModelYear IS NULL OR fkModelYear={self.model_year}) AND
            (fkPartnerGroup IS NULL OR fkPartnerGroup={self.partner_group}) AND
            (fkEngine IS NULL OR fkEngine={self.engine}) AND
            (fkTransmission IS NULL OR fkTransmission={self.transmission}) AND
            fkBodyStyle IS NULL AND
            fkSteering IS NULL AND
            fkNodeECU IS NULL AND
            fkSpecialVehicle IS NULL
        """).df()
        return profiles['Id'].tolist()

    @staticmethod
    def get_value_description(key: str) -> str:
        # We use getattr here so the names from read_csv.DatabaseFile need to match up with our member variable names
        values = duckdb.execute(f"SELECT Description FROM {key} WHERE Id=?", [getattr(vehicle, key)]).df()
        if values.empty:
            raise ValueError(f'Invalid Vehicle: {key} not valid')
        return values['Description'].iloc[0]
    
    def print(self):
        """
        Pretty-prints the information from a vehicle.
        """
        get_csv(DatabaseFile.vehicle_model)
        get_csv(DatabaseFile.model_year)
        get_csv(DatabaseFile.body_style)
        get_csv(DatabaseFile.partner_group)
        get_csv(DatabaseFile.engine)
        get_csv(DatabaseFile.transmission)

        print(f'Model: {self.get_value_description("vehicle_model")} [{self.vehicle_model}]')
        print(f'Year: {self.get_value_description("model_year")} [{self.model_year}]')
        print(f'Partner: {self.get_value_description("partner_group")} [{self.partner_group}]')
        print(f'Engine: {self.get_value_description("engine")} [{self.engine}]')
        print(f'Transmission: {self.get_value_description("transmission")} [{self.transmission}]')
        print(f'VIDA Profiles: {self.get_vehicle_profiles()}')


def decode_vin(vin: str) -> Vehicle:
    """
    Decodes the VIN to find model information such as model id, model year, partner group, engine and transmission information,
    based on information from the VIDA database.
    There's more information inside the VIN number, which is not decoded here. You can find more information here:
    https://en.wikibooks.org/wiki/Vehicle_Identification_Numbers_(VIN_codes)/Volvo/VIN_Codes#Position_1_-_3:_World_Manufacturer_Identifier
    """
    if vin[:3] != 'YV1':
        print('VIN is not for a Volvo vehicle')
        return
    
    # Load the CSV files
    decode_model = get_csv(DatabaseFile.vin_decode_model).df()
    decode_variant = get_csv(DatabaseFile.vin_decode_variant).df()
    #get_csv(DatabaseFile.vin_variant_codes)

    # Use the VINDecodeModel table to get vehicle model, year, and group information
    decoded_model = None
    for _, row in decode_model.iterrows():
        compare_val = vin[row['VinStartPos']-1:row['VinEndPos']]
        chassis_no = int(vin[11:])

        if compare_val == row['VinCompare'] and chassis_no >= int(row['ChassisNoFrom']) and chassis_no <= int(row['ChassisNoTo']) and row['fkPartnerGroup'] == 1002:
            decoded_model = Model(row)
            break

    # Use the decoded information to get engine and transmission values
    # Sometimes there's more than one engine or transmission for one VIN.
    engines = []
    transmissions = []
    for _, row in decode_variant.iterrows():
        # Filter for already detected model variants
        if Model(row) != decoded_model:
            continue

        compare_val = vin[row['VinStartPos']-1:row['VinEndPos']]
        if compare_val != row['VinCompare']:
            continue

        # The table only includes either the engine or the transmission.
        if not math.isnan(row['fkEngine']):
            engines.append(int(row['fkEngine']))
        if not math.isnan(row['fkTransmission']):
            transmissions.append(int(row['fkTransmission']))

    if not engines or not transmissions:
        raise ValueError('Failed to find a valid engine or transmission')
    
    # If there's only one engine and one transmission for this VIN, return that.
    if len(engines) == 1 and len(transmissions) == 1:
        return Vehicle(decoded_model, engines[0], transmissions[0])

    # To exclude combinations of engine and transmission we'll now go through the vehicle profiles
    # and check if any profile exists with both combinations.
    get_csv(DatabaseFile.vehicle_profile)
    for engine in engines:
        for transmission in transmissions:
            combination = duckdb.sql(f"""
                SELECT * FROM vehicle_profile
                WHERE fkVehicleModel = {decoded_model.vehicle_model} AND
                fkModelYear = {decoded_model.model_year} AND
                fkPartnerGroup = {decoded_model.partner_group} AND
                fkEngine = {engine} AND
                fkTransmission = {transmission}
            """).df()
            if not combination.empty:
                return Vehicle(decoded_model, engine, transmission)

    # Not a valid VIN
    raise ValueError('Found no valid combination of engine and transmission')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: vin_decoder.py <VIN>')
    else:
        vehicle = decode_vin(sys.argv[1])
        vehicle.print()
