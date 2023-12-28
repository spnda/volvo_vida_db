#!/usr/bin/env python3

from vin_decoder import PartnerGroup, decode_vin
from read_csv import DatabaseFile, get_csvs

# These are some VINs I found in the VIDA source code which are used for testing I think.
# Entering x0000000000000000 where x is any digit into the VIN input in VIDA will transform into
# the i-ths VIN in the below list. The last two VINs seem to be left-over from testing code in VIDA.
test_vins = [("YV1LZ56DXY2736349", PartnerGroup.AME),
            ("YV1LW5642W2360395", PartnerGroup.EUR),
            ("YV1945866W1234629", PartnerGroup.EUR),
            ("YV1LS61F2Y2667227", PartnerGroup.EUR),
            ("YV1SW61P212048331", PartnerGroup.EUR),
            # "YV1LW65F2Y683325", <-- Found in VIDA but actually invalid.
            ("YV1RS65P212000500", PartnerGroup.EUR),
            ("YV1RS65P922122056", PartnerGroup.EUR),
            # "YV1TS61R91193741", <-- Also not a valid VIN
            ("YV1RS59G242370046", PartnerGroup.EUR),
            ("YV1TS61F2Y1065654", PartnerGroup.EUR),
            ("YV1KS960XV1104523", PartnerGroup.AME)]

get_csvs(DatabaseFile.vehicle_model, DatabaseFile.model_year, DatabaseFile.partner_group, DatabaseFile.body_style, DatabaseFile.engine, DatabaseFile.transmission)
for vin, partner in test_vins:
    try:
        vehicle = decode_vin(vin, partner_id=partner, cached=False)
        print(vehicle.get_value_description("vehicle_model"))
        #vehicle.print()
    except ValueError as e:
        print("Failed lookup: " + str(e))
