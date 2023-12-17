import sys
import duckdb
import pandas as pd
from read_csv import get_csv, DatabaseFile, root_directory
from vin_decoder import decode_vin, Vehicle

def get_filtered_scripts_for_profile(profile: str) -> list[str]:
    """
    Returns all script IDs available for given profile
    """
    get_csv(DatabaseFile.script_profile_map)
    return duckdb.sql(f"""
        SELECT fkScript FROM script_profile_map
        WHERE TRIM(fkProfile) = '{profile}'
    """).df()['fkScript'].tolist()


def get_filtered_scripts(profiles: list[str]) -> pd.DataFrame:
    """
    Returns all script IDs available for all given profiles.
    This is intended where one vehicle is represented by multiple profiles,
    not for querying scripts for multiple vehicles.
    """
    get_csv(DatabaseFile.script_profile_map)
    profiles_df = pd.DataFrame(profiles, columns=['fkProfile'])
    return duckdb.sql("""
        SELECT DISTINCT fkScript FROM script_profile_map
        INNER JOIN profiles_df ON profiles_df.fkProfile=TRIM(script_profile_map.fkProfile)
    """).df()


def get_script_descriptions(scripts: pd.DataFrame) -> pd.DataFrame:
    get_csv(DatabaseFile.script_content)
    return duckdb.sql("""
        SELECT DISTINCT scripts.fkScript,script_content.DisplayText FROM scripts
        INNER JOIN script_content ON script_content.fkScript=scripts.fkScript
    """).df()


def get_script_description(script_id: str) -> str:
    get_csv(DatabaseFile.script_content)
    return duckdb.sql(f"SELECT fkScript,DisplayText FROM script_content WHERE fkScript='{script_id}'").df()['DisplayText'].iloc[0]


if __name__ == '__main__':
    profiles = []

    if len(profiles) == 0 and len(sys.argv) == 1:
        print("Usage: filter_scripts.py <VIN>")
    else:
        if len(profiles) == 0:
            vehicle = decode_vin(sys.argv[1])
            profiles = vehicle.get_vehicle_profiles()
        
        scripts = get_filtered_scripts(profiles)
        scripts = get_script_descriptions(scripts)
        duckdb.write_csv(scripts, f"{root_directory}/ecu/scripts.csv")
