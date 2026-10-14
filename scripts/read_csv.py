import duckdb
import enum
import os

loaded_csv_dictionary = {}
# Directory containing the csv/ folder (and optionally vida.duckdb). Defaults to the working directory, but can be
# overridden with the VIDA_ROOT environment variable or set_cwd().
root_directory = os.environ.get('VIDA_ROOT', os.getcwd())

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
    amy_profile_map = 'basedata/AMYProfileMap'
    node_ecu = 'basedata/NodeECU'
    special_vehicle = 'basedata/SpecialVehicle'
    steering = 'basedata/Steering'
    vehicle_profile_partner_group = 'basedata/VehicleProfilePartnerGroup'
    t100 = 'carcom/T100_EcuVariant'
    t101 = 'carcom/T101_Ecu'
    t102 = 'carcom/T102_EcuType'
    t110 = 'carcom/T110_Service_EcuVariant'
    t111 = 'carcom/T111_Service'
    t120 = 'carcom/T120_Config_EcuVariant'
    t121 = 'carcom/T121_Config'
    t122 = 'carcom/T122_Protocol'
    t123 = 'carcom/T123_Bus'
    t124 = 'carcom/T124_Net'
    t130 = 'carcom/T130_Init'
    t131 = 'carcom/T131_InitValue'
    t132 = 'carcom/T132_InitValueType'
    t133 = 'carcom/T133_InitCategory'
    t136 = 'carcom/T136_InitHw_Profile'
    t137 = 'carcom/T137_InitSwdl_Profile'
    t141 = 'carcom/T141_Block'
    t142 = 'carcom/T142_BlockType'
    t143 = 'carcom/T143_BlockDataType'
    t144 = 'carcom/T144_BlockChild'
    t148 = 'carcom/T148_BlockMetaPARA'
    t150 = 'carcom/T150_BlockValue'
    t151 = 'carcom/T151_BlockValue_Symptom'
    t152 = 'carcom/T152_Symptom'
    t153 = 'carcom/T153_SymptomCategory'
    t154 = 'carcom/T154_SymptomType'
    t155 = 'carcom/T155_Scaling'
    t156 = 'carcom/T156_SymptomSection'
    t157 = 'carcom/T157_SymptomConnection'
    t158 = 'carcom/T158_Symptom_CSC'
    t159 = 'carcom/T159_SymptomCSC_SymptomDTC'
    t160 = 'carcom/T160_DefaultEcuVariant'
    t161 = 'carcom/T161_Profile'
    t162 = 'carcom/T162_ProfileValue'
    t163 = 'carcom/T163_ProfileValueType'
    t170 = 'carcom/T170_SecurityCode_EcuVariant'
    t171 = 'carcom/T171_SecurityCode'
    t172 = 'carcom/T172_SecurityCodeType'
    t190 = 'carcom/T190_Text'
    t191 = 'carcom/T191_TextData'
    t192 = 'carcom/T192_TextCategory'
    t193 = 'carcom/T193_Language'
    t194 = 'carcom/T194_FunctionGroup_1'
    t196 = 'carcom/T196_FunctionGroup_2'
    script = 'DiagSwdlRepository/Script'
    script_car_function = 'DiagSwdlRepository/ScriptCarFunction'
    script_content = 'DiagSwdlRepository/ScriptContent'
    script_profile_map = 'DiagSwdlRepository/ScriptProfileMap'
    script_type = 'DiagSwdlRepository/ScriptType'
    script_variant = 'DiagSwdlRepository/ScriptVariant'
    graphic_formats = 'imagerepository/GraphicFormats'
    graphics = 'imagerepository/Graphics'
    localized_graphics = 'imagerepository/LocalizedGraphics'

# Columns that have to be read as text, although they often look like numbers: hex values like '10' or '7A',
# identifiers with leading zeros or significant spaces, and compare values like '0x1A04'.
TEXT_COLUMNS = {
    DatabaseFile.t100: ['identifier'],
    DatabaseFile.t101: ['identifier'],
    DatabaseFile.t102: ['identifier'],
    DatabaseFile.t111: ['service', 'mode'],
    DatabaseFile.t121: ['physicalAddress', 'functionalAddress', 'canAddress', 'commAddress',
                        'canIdTX', 'canIdRX', 'canIdFunc', 'canIdUUDT'],
    DatabaseFile.t131: ['initValue'],
    DatabaseFile.t137: ['ecuAddress'],
    DatabaseFile.t150: ['CompareValue', 'altDisplayValue'],
    DatabaseFile.t155: ['definition'],
    DatabaseFile.t162: ['identifier', 'description'],
    DatabaseFile.t171: ['code'],
    DatabaseFile.vin_decode_model: ['VinCompare', 'YearCode'],
    DatabaseFile.vin_decode_variant: ['VinCompare'],
    DatabaseFile.vin_variant_codes: ['VINVariantCode'],
    DatabaseFile.script_car_function: ['FunctionGroup'],
}

def csv_path(csv_file: DatabaseFile) -> str:
    return os.path.join(root_directory, 'csv', f'{csv_file.value}.csv')

def database_path() -> str:
    """
    Location of the optional DuckDB database created by build_database.py.
    """
    return os.path.join(root_directory, 'vida.duckdb')

def read_csv_file(csv_file: DatabaseFile, connection: duckdb.DuckDBPyConnection = None) -> duckdb.DuckDBPyRelation:
    """
    Reads one of the CSV files. The column types are detected from the whole file (sample_size=-1), except for
    the columns in TEXT_COLUMNS.
    """
    connection = connection or duckdb.default_connection()
    text_columns = {column: 'VARCHAR' for column in TEXT_COLUMNS.get(csv_file, [])}
    return connection.read_csv(csv_path(csv_file), header=True, encoding='utf-8', sample_size=-1,
                               dtype=text_columns or None)

_database_attached = False

def _attach_database() -> bool:
    """
    Attaches vida.duckdb to the default connection as 'vida', if it exists and VIDA_NO_DATABASE is not set.
    """
    global _database_attached
    if not _database_attached and not os.environ.get('VIDA_NO_DATABASE') and os.path.exists(database_path()):
        duckdb.sql(f"ATTACH '{database_path()}' AS vida (READ_ONLY)")
        _database_attached = True
    return _database_attached

def get_csv(csv_file: DatabaseFile) -> duckdb.DuckDBPyRelation:
    """
    Loads a possibly cached relation for the specific file and registers it under the enum member name (e.g. t141),
    so it can be referenced in SQL queries. The data comes from vida.duckdb if it exists, else from the CSV file.
    """
    if csv_file not in loaded_csv_dictionary:
        if _attach_database():
            duckdb.sql(f'CREATE OR REPLACE TEMP VIEW {csv_file.name} AS SELECT * FROM vida.{csv_file.name}')
            relation = duckdb.table(csv_file.name)
        else:
            relation = read_csv_file(csv_file)
            duckdb.register(csv_file.name, relation)
        loaded_csv_dictionary[csv_file] = relation
    return loaded_csv_dictionary[csv_file]

def get_csvs(*csv_files: DatabaseFile):
    for file in csv_files:
        get_csv(file)

def set_cwd(path: str):
    """
    Change the directory in which to look for the VIDA CSV files
    """
    global root_directory
    root_directory = path
