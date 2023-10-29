from enum import Enum

import pandas as pd
import duckdb
import inquirer

from read_csv import t161, t162, t163

class ProfileValueType(Enum):
    MODEL_ID = 'model_id'
    MODEL_YEAR = 'model_year'
    ENGINE = 'engine'
    TRANSMISSION = 'transmission'
    BODY = 'body'
    STEERING = 'steering'
    MARKET = 'market'

def get_sql_key(type: ProfileValueType) -> str:
    return {
        ProfileValueType.MODEL_ID: 'fkT162_ProfileValue_Model',
        ProfileValueType.MODEL_YEAR: 'fkT162_ProfileValue_Year',
        ProfileValueType.ENGINE: 'fkT162_ProfileValue_Engine',
        ProfileValueType.TRANSMISSION: 'fkT162_ProfileValue_Transmission',
        ProfileValueType.BODY: 'fkT162_ProfileValue_Body',
        ProfileValueType.STEERING: 'fkT162_ProfileValue_Steering',
        ProfileValueType.MARKET: 'fkT162_ProfileValue_Market',
    }[type]

def get_profile_values() -> pd.DataFrame:
    return duckdb.query("""
        SELECT pv.id, pv.identifier, pv.description, pvt.identifier as type FROM t162 pv
        INNER JOIN t163 pvt ON pvt.id=pv.fkT163_ProfileValueType
    """).to_df()

def filter_profile_values(frame: pd.DataFrame, type: ProfileValueType) -> pd.DataFrame:
    # Filter DataFrame by joined value type
    return frame.loc[frame['type'].str.contains(type.value)]

def get_profile_value_id(frame: pd.DataFrame, value: str) -> int:
    # Get profile value ID from description string
    return duckdb.query(f"SELECT id FROM t162 WHERE description='{value}'").to_df()['id'].tolist()[0]

def find_vehicle_profiles() -> list[str]:
    render = inquirer.render.ConsoleRender(theme=inquirer.themes.Default())
    fields = [
        ProfileValueType.MODEL_ID,
        ProfileValueType.MODEL_YEAR,
        ProfileValueType.ENGINE,
        ProfileValueType.TRANSMISSION,
        ProfileValueType.BODY,
        ProfileValueType.STEERING,
        ProfileValueType.MARKET,
    ]
    values = get_profile_values()
    possible_profiles = t161.copy()
    profile_ids = []

    # This function first starts with an entire copy of the T161_Profile table with all vehicle profiles,
    # and then slowly filters the table using user input on specific vehicle profile values from table T162_ProfileValue.
    for idx, type in enumerate(fields):
        if idx>=3:
            break

        # Get the possible value descriptions for the current type from all possible vehicle profiles.
        possible_values = duckdb.query(f"""
            SELECT DISTINCT pv.description, p.{get_sql_key(type)} FROM possible_profiles p
            INNER JOIN t162 pv ON pv.id=p.{get_sql_key(type)}
            WHERE folderLevel={idx+1}
            ORDER BY pv.description
        """).to_df()

        # Convert to tuples to make use of inquirer's list tagging.
        tuples = list(possible_values.itertuples(index=False))
        question = inquirer.List(type.value, message=f"Select {type.value}", choices=tuples)
        answer = render.render(question, None)

        # Filter the possible profiles by the selected value in the respective column.
        possible_profiles = duckdb.query(f"""
            SELECT * FROM possible_profiles p
            WHERE p.{get_sql_key(type)}={answer}
        """).to_df()

        # Get the selected profile ID (there should only be 1 at this level)
        selected_profiles = duckdb.query(f"SELECT identifier FROM possible_profiles WHERE folderLevel={idx+1} AND {get_sql_key(type)}={answer}").to_df()
        profile_ids.append(selected_profiles['identifier'].tolist()[0])

    return profile_ids

if __name__ == '__main__':
    profile_ids = find_vehicle_profiles()
    print(f"List of selected vehicle profiles: {profile_ids}")
