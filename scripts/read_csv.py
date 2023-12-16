import duckdb
import enum
import os

loaded_csv_dictionary = {}
root_directory = os.getcwd()

class DatabaseFile(str, enum.Enum):
    body_style = 'basedata/BodyStyle'
    engine = 'basedata/Engine'
    model_year = 'basedata/ModelYear'
    partner_group = 'basedata/PartnerGroup'
    transmission = 'basedata/Transmission'
    vehicle_model = 'basedata/VehicleModel'
    vehicle_profile = 'basedata/VehicleProfile'
    vin_decode_model = 'basedata/VINDecodeModel'
    vin_decode_variant = 'basedata/VINDecodeVariant'
    vin_variant_codes = 'basedata/VINVariantCodes'
    t100 = 'carcom/T100_EcuVariant'
    t101 = 'carcom/T101_Ecu'
    t102 = 'carcom/T102_EcuType'
    t120 = 'carcom/T120_Config_EcuVariant'
    t121 = 'carcom/T121_Config'
    t141 = 'carcom/T141_Block'
    t142 = 'carcom/T142_BlockType'
    t144 = 'carcom/T144_BlockChild'
    t150 = 'carcom/T150_BlockValue'
    t155 = 'carcom/T155_Scaling'
    t160 = 'carcom/T160_DefaultEcuVariant'
    t161 = 'carcom/T161_Profile'
    t162 = 'carcom/T162_ProfileValue'
    t163 = 'carcom/T163_ProfileValueType'
    t191 = 'carcom/T191_TextData'
    script = 'DiagSwdlRepository/Script'
    script_car_function = 'DiagSwdlRepository/ScriptCarFunction'
    script_content = 'DiagSwdlRepository/ScriptContent'
    script_profile_map = 'DiagSwdlRepository/ScriptProfileMap'
    script_type = 'DiagSwdlRepository/ScriptType'
    script_variant = 'DiagSwdlRepository/ScriptVariant'

def get_csv(csv_file: DatabaseFile) -> duckdb.DuckDBPyRelation:
    """
    Loads a possibly cached dataframe for the specific file
    """
    if csv_file in loaded_csv_dictionary:
        return loaded_csv_dictionary[csv_file]
    else:
        loaded_csv_dictionary[csv_file] = duckdb.read_csv(f'{root_directory}/csv/{csv_file}.csv', header=True, encoding='utf-8')
        duckdb.register(csv_file.name, loaded_csv_dictionary[csv_file])
        return loaded_csv_dictionary[csv_file]
    
def get_csvs(*csv_files: DatabaseFile):
    for file in csv_files:
        get_csv(file)

def set_cwd(path: str):
    """
    Change the directory in which to look for the VIDA CSV files
    """
    root_directory = path
