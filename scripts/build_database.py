#!/usr/bin/env python3
"""
Imports the VIDA CSV files into a single DuckDB database file, vida.duckdb.

The largest CSV files (T141_Block, T144_BlockChild, T150_BlockValue) are several hundred megabytes and take long to
parse. Once vida.duckdb exists, read_csv.get_csv reads the tables from it instead, which makes queries much faster.

Every file listed in read_csv.DatabaseFile becomes a table named after the enum member (t141, vehicle_profile, ...),
read exactly like get_csv would read the CSV file. To add a table, add it to DatabaseFile.

Usage: build_database.py [--force]
"""

import argparse
import os
import sys
import time

import duckdb

from read_csv import DatabaseFile, csv_path, database_path, read_csv_file


def build_database(output: str):
    with duckdb.connect(output) as connection:
        for csv_file in DatabaseFile:
            if not os.path.exists(csv_path(csv_file)):
                print(f'{csv_file.name}: {csv_path(csv_file)} not found, skipped')
                continue

            start = time.time()
            read_csv_file(csv_file, connection).create(csv_file.name)
            rows = connection.table(csv_file.name).count('*').fetchone()[0]
            print(f'{csv_file.name}: {rows} rows ({time.time() - start:.1f}s)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import the VIDA CSV files into vida.duckdb.')
    parser.add_argument('--force', action='store_true', help='Replace an existing vida.duckdb')
    args = parser.parse_args()

    output = database_path()
    if os.path.exists(output):
        if not args.force:
            sys.exit(f'{output} already exists, use --force to rebuild it.')
        os.remove(output)
    build_database(output)
