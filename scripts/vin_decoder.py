#!/usr/bin/env python3

import math
import sys
import duckdb
import pandas
import pickle
import os
from enum import Enum
from read_csv import get_csv, get_csvs, DatabaseFile, root_directory

# These values are copied from the SQL table basedata/PartnerGroup
class PartnerGroup(Enum):
    AME = 1001
    EUR = 1002
    INT = 1003
    NOR = 1004
    CHI = 1005

# Represents a decoded vehicle from a VIN
class Vehicle:
    def __init__(self, vin: str, row: pandas.Series):
        self.vin = vin
        self.vehicle_model = row['fkVehicleModel']
        self.model_year = row['fkModelYear']
        self.partner_group = row['fkPartnerGroup']
        self.body_style = row['fkBodyStyle'] if row['fkBodyStyle'] != -1 else 0
        self.engine = row['fkEngine']
        self.transmission = row['fkTransmission']

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
            (fkBodyStyle IS NULL OR fkBodyStyle={self.body_style}) AND
            fkSteering IS NULL AND
            fkNodeECU IS NULL AND
            fkSpecialVehicle IS NULL
        """).df()
        return profiles['Id'].tolist()

    def get_value_description(self, key: str) -> str:
        value = getattr(self, key)
        if value is None or value == 0:
            return ""
        
        # We use getattr here so the names from read_csv.DatabaseFile need to match up with our member variable names
        values = duckdb.execute(f"SELECT Description FROM {key} WHERE Id=?", [int(value)]).df() # somehow the getattr thing works with float64, but not with int64...
        if values.empty:
            raise ValueError(f'Invalid Vehicle: {key} not valid')
        return values['Description'].iloc[0]
    
    def print(self):
        """
        Pretty-prints the information from a vehicle.
        """
        get_csvs(DatabaseFile.vehicle_model, DatabaseFile.model_year, DatabaseFile.partner_group, DatabaseFile.body_style, DatabaseFile.engine, DatabaseFile.transmission)

        print(f'Model: {self.get_value_description("vehicle_model")} [{self.vehicle_model}]')
        print(f'Year: {self.get_value_description("model_year")} [{self.model_year}]')
        print(f'Partner: {self.get_value_description("partner_group")} [{self.partner_group}]')
        print(f'Body: {self.get_value_description("body_style")} [{self.body_style}]')
        print(f'Engine: {self.get_value_description("engine")} [{self.engine}]')
        print(f'Transmission: {self.get_value_description("transmission")} [{self.transmission}]')
        print(f'VIDA Profiles: {self.get_vehicle_profiles()}')

def validate_vin(vin: str) -> bool:
    vin = vin.strip()
    if len(vin) != 17:
        return False
    chassis_no = vin[11:]
    return chassis_no.isdigit()

# TODO: Don't default to PartnerGroup.EUR but have some detection or add it as a required input for all callers.
def decode_vin(vin: str, partner_id: PartnerGroup = PartnerGroup.EUR, cached: bool = True) -> Vehicle:
    """
    Decodes the VIN to find model information such as model id, model year, partner group, engine and transmission information,
    based on information from the VIDA database.
    There's more information inside the VIN number, which is not decoded here. You can find more information here:
    https://en.wikibooks.org/wiki/Vehicle_Identification_Numbers_(VIN_codes)/Volvo/VIN_Codes#Position_1_-_3:_World_Manufacturer_Identifier
    """
    if not validate_vin(vin):
        raise ValueError('VIN string is not a valid VIN')
    
    if vin[:3] != 'YV1':
        raise ValueError('VIN is not for a Volvo vehicle')
    
    if cached and os.path.exists(f"cache/{vin}.p"):
        # This import is to avoid namespace problems, making the class always be vin_decoder.Vehicle instead of __main__.Vehicle
        from vin_decoder import Vehicle
        return pickle.load(open(f"{root_directory}/cache/{vin}.p", "rb"))
    
    get_csv(DatabaseFile.vin_decode_model)
    get_csv(DatabaseFile.vin_decode_variant)

    # Use the VINDecodeModel and VINDecodeVariant tables. The tables provide values for a substring operation and a comparison value.
    # Using that, the chassis number (last 6 digits) and the year code (from VM.Yearcodepos), we can identify the vehicle.
    # We specifically do not use duckdb.execute here, as converting to a pandas DataFrame currently converts the int64 column to a float column
    # with NULL values being converted to float NaNs.
    components = duckdb.sql(f"""
        SELECT VM.fkVehicleModel, VM.fkModelYear, VM.fkPartnerGroup, VM.fkBodyStyle, VV.fkEngine, VV.fkTransmission
        FROM vin_decode_model as VM, vin_decode_variant as VV
        WHERE VM.fkVehicleModel = VV.fkVehicleModel
        AND VM.fkModelYear = VV.fkModelYear
        AND (SUBSTRING('{vin}' from VM.VinStartPos for VM.VinEndPos - VM.VinStartPos + 1) = VM.VinCompare)
        AND (SUBSTRING('{vin}' from VV.VinStartPos for VV.VinEndPos - VV.VinStartPos + 1) = VV.VinCompare)
        AND (RIGHT('{vin}', 6) BETWEEN VM.ChassisNoFrom AND VM.ChassisNoTo)
        AND (VM.Yearcode = SUBSTRING('{vin}', VM.Yearcodepos, 1) OR VM.Yearcode IS NULL)
        AND VM.fkPartnerGroup = VV.fkPartnerGroup
        AND VM.fkPartnerGroup = {partner_id.value}
    """)

    # For cases where the VIN represents multiple combinations of engines and transmissions we match the table with itself to create
    # rows with every possible combination of engines and transmissions.
    # However, we also want to allow VINs where the transmission is not determinable or where no transmission is specified in the database.
    combined = duckdb.sql("""
        SELECT DISTINCT c1.fkVehicleModel, c1.fkModelYear, c1.fkPartnerGroup, c1.fkBodyStyle, c1.fkEngine, c2.fkTransmission FROM components AS c1, components AS c2
        WHERE (c1.fkEngine IS NOT NULL AND c2.fkTransmission IS NOT NULL) OR (c1.fkEngine IS NOT NULL AND c2.fkTransmission IS NULL AND NOT EXISTS (
            SELECT 1 FROM components WHERE fkTransmission IS NOT NULL
        ))
    """).df()

    # Filter all the engine/transmission combinations for actually valid ones from the VehicleProfile table if more than one exists
    if len(combined) > 1:
        get_csv(DatabaseFile.vehicle_profile)
        filtered = duckdb.sql("""
            SELECT DISTINCT combined.* FROM combined
            INNER JOIN vehicle_profile vp on vp.fkVehicleModel=combined.fkVehicleModel AND vp.fkModelYear=combined.fkModelYear
            WHERE (combined.fkEngine=vp.fkEngine AND combined.fkTransmission=vp.fkTransmission) OR combined.fkTransmission IS NULL
        """).df()
        combined = filtered

    # Replace possible NaN values with 'None' to avoid having float64 columns, and cast everything to int to not use numpy types
    combined = combined.replace({math.nan: 0}).astype('int64')

    if combined.empty:
        raise ValueError('Failed to find valid vehicles for VIN')
    if len(combined['fkVehicleModel'].unique()) > 1:
        # Only the vehicle model has to be unique. All other values can technically be unspecified by the VIN.
        raise ValueError('More than 1 vehicle appeared for VIN')
    
    from vin_decoder import Vehicle
    vehicle = Vehicle(vin, combined.loc[0])
    if cached:
        if not os.path.isdir("cache"):
            os.makedirs("cache")
        pickle.dump(vehicle, open(f"{root_directory}/cache/{vin}.p", "wb"))
    return vehicle

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: vin_decoder.py <VIN>')
    else:
        try:
            vehicle = decode_vin(sys.argv[1], cached=False)
            vehicle.print()
        except ValueError as e:
            print("Failed to decode VIN: " + str(e))
