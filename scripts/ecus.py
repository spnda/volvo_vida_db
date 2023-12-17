import pandas as pd
import duckdb

from read_csv import get_csv, get_csvs, DatabaseFile

def get_ecu_type(identifier: int) -> duckdb.DuckDBPyRelation:
    get_csv(DatabaseFile.t102)
    return duckdb.sql(f"""
       SELECT * FROM t102 WHERE identifier={identifier}
    """)

def get_block_types() -> duckdb.DuckDBPyRelation:
    get_csv(DatabaseFile.t142)
    return duckdb.sql("""
        SELECT id, identifier, fkT142_BlockType_Parent AS parent
        FROM t142 
    """)

def get_ecu_addresses() -> duckdb.DuckDBPyRelation:
    get_csvs(DatabaseFile.t120, DatabaseFile.t121, DatabaseFile.t100, DatabaseFile.t101, DatabaseFile.t102, DatabaseFile.t191)
    return duckdb.sql("""
        SELECT DISTINCT t121.commAddress as address, t102.identifier, t191.data as title
        FROM t121
        INNER JOIN t120 ON t120.fkT121_Config = t121.id
        INNER JOIN t100 ON t100.id = t120.fkT100_EcuVariant
        INNER JOIN t101 ON t101.id = t100.fkT101_Ecu
        INNER JOIN t102 ON t102.id = t101.fkT102_EcuType
        INNER JOIN t191 ON t191.fkT190_Text = t102.fkT190_Text AND t191.fkT193_Language = 19
        ORDER BY address
    """)

def get_ecu_types() -> duckdb.DuckDBPyRelation:
    """
    Returns all ECU type IDs together with their human-readable name.
    """
    get_csvs(DatabaseFile.t102, DatabaseFile.t191)
    return duckdb.sql("""
        SELECT DISTINCT t102.id, t102.identifier, td.data
        FROM t102
        INNER JOIN t191 td ON t102.fkT190_Text = td.fkT190_Text
        WHERE t102.identifier != '0' AND td.fkT192_Language = 19 AND len(t102.identifier) = 6
        ORDER BY t102.identifier
    """)

def get_ecu_identifiers(profile_identifier: str) -> duckdb.DuckDBPyRelation:
    """
    Returns all ECUs linked to the given vehicle profile with their ID, variant ID, type ID, and name.
    """
    get_csvs(DatabaseFile.t160, DatabaseFile.t161, DatabaseFile.t100, DatabaseFile.t101, DatabaseFile.t102)
    return duckdb.sql(f"""
        SELECT p.title, e.identifier AS EcuIdentifier, e.name AS EcuName, ev.identifier AS EcuVariantIdentifier, et.identifier AS EcuTypeIdentifier
        FROM t161 p
        INNER JOIN t160 dev ON dev.fkT161_Profile = p.id
        INNER JOIN t100 ev ON ev.id = dev.fkT100_EcuVariant
        INNER JOIN t101 e ON e.id = ev.fkT101_Ecu
        INNER JOIN t102 et ON et.id = e.fkT102_EcuType
        WHERE p.identifier = '{profile_identifier}'
        ORDER BY e.identifier
    """)

def get_ecu_config(ecu_identifier: str) -> duckdb.DuckDBPyRelation:
    """
    Returns the communication config for a specific ECU variant by its identifier, like e.g. '31211150 AA'.
    A list of all variant identifiers can be acquired through get_ecu_identifiers and its EcuIdentifier column.
    This returns all of the columns from the T121_Config table, joined with other important information about
    this specific ECU, such as the ID, name and type.
    """
    get_csvs(DatabaseFile.t100, DatabaseFile.t120, DatabaseFile.t121)
    return duckdb.sql(f"""
        SELECT DISTINCT ev.id, ev.identifier, e.identifier, e.fkT102_EcuType, et.description,
                      c.id,
                      c.fkT123_Bus, c.fkT122_Protocol, c.fkT130_Init_Diag, c.fkT130_Init_Timing, c.physicalAddress,
                      c.functionalAddress, c.canAddress, c.commAddress, c.priority, c.canIdTX, c.canIdRX,
                      c.canIdFunc, c.canIdUUDT, c.busRate, c.addressSize, c.fkT121_Config_Gateway
            FROM t100 ev
            INNER JOIN t101 e ON e.id=ev.fkT101_Ecu
            INNER JOIN t102 et ON et.id=e.fkT102_EcuType
            INNER JOIN t120 cev ON cev.fkT100_EcuVariant=ev.id
            INNER JOIN t121 c ON c.id=cev.fkT121_Config
            WHERE ev.identifier='{ecu_identifier}'
    """)

def get_can_parameters(ecu_identifier: str) -> duckdb.DuckDBPyRelation:
    get_csvs(DatabaseFile.t100, DatabaseFile.t144, DatabaseFile.t141, DatabaseFile.t150, DatabaseFile.t155, DatabaseFile.t191)
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
    """)
