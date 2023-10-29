import pandas as pd

def get_csv_df(csv_file) -> pd.DataFrame:
    return pd.read_csv(f'csv/{csv_file}.csv', encoding='latin-1')

t100 = get_csv_df('carcom/T100_EcuVariant')
t101 = get_csv_df('carcom/T101_Ecu')
t102 = get_csv_df('carcom/T102_EcuType')
t141 = get_csv_df('carcom/T141_Block')
t144 = get_csv_df('carcom/T144_BlockChild')
t150 = get_csv_df('carcom/T150_BlockValue')
t155 = get_csv_df('carcom/T155_Scaling')
t160 = get_csv_df('carcom/T160_DefaultEcuVariant')
t161 = get_csv_df('carcom/T161_Profile')
t162 = get_csv_df('carcom/T162_ProfileValue')
t163 = get_csv_df('carcom/T163_ProfileValueType')
t191 = get_csv_df('carcom/T191_TextData')
