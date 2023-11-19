import duckdb
import enum

loaded_csv_dictionary = {}

class DatabaseFile(str, enum.Enum):
    t100 = 'carcom/T100_EcuVariant'
    t101 = 'carcom/T101_Ecu'
    t102 = 'carcom/T102_EcuType'
    t141 = 'carcom/T141_Block'
    t144 = 'carcom/T144_BlockChild'
    t150 = 'carcom/T150_BlockValue'
    t155 = 'carcom/T155_Scaling'
    t160 = 'carcom/T160_DefaultEcuVariant'
    t161 = 'carcom/T161_Profile'
    t162 = 'carcom/T162_ProfileValue'
    t163 = 'carcom/T163_ProfileValueType'
    t191 = 'carcom/T191_TextData'

def get_csv(csv_file: DatabaseFile) -> duckdb.DuckDBPyRelation:
    """
    Loads a possibly cached dataframe for the specific file
    """
    if csv_file in loaded_csv_dictionary:
        return loaded_csv_dictionary[csv_file]
    else:
        loaded_csv_dictionary[csv_file] = duckdb.read_csv(f'csv/{csv_file}.csv', encoding='utf-8')
        duckdb.register(csv_file.name, loaded_csv_dictionary[csv_file])
        return loaded_csv_dictionary[csv_file]
