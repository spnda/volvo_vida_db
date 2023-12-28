#!/usr/bin/env python3

from read_csv import get_csv, DatabaseFile
from evaluate_conversion import evaluate_conversion

# Small script to test if evaluate_conversion.py covers all cases in the VIDA db
df = get_csv(DatabaseFile.t155).df()
for index, row in df.iterrows():
    expression = row['definition']
    
    # No idea what this is supposed to do: https://stackoverflow.com/questions/77385619/as-a-data-conversion-operator
    # I guess its just some typo in the database?
    if expression=='x*/32+8':
        continue

    # There's a dedicated SQL column for the Unit... Why is it in the expression?
    if expression=='x*cm^3/s':
        continue
    
    try:
        print(f"\nEvaluating {expression}...")
        print(f"With x=1, {expression} = {evaluate_conversion(1, expression)}")
    except ZeroDivisionError:
        print(f"Artihmetic issue with {expression}. Likely just unsuitable mock input data.")
    except SyntaxError:
        print(f"Failed to parse {expression}")
    except TypeError as type_error:
        print(f"Failed to run AST of {expression}: {type_error}")

# Some additional tests for other possible expressions.
# Some operators used here are not used in the T155 table but are theoretically implemented in VIDA.
# See Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Calculator
expressions = [
    ("0b0001|0b0010", 3),
    ("int(1.5)", 2),
    ("int(log(3)+ln(3))", 2),
    ("3*(-1)+3", 0),
    ("10&0b11001010", 10),
    ("10&0xF", 10),
    ("(0x0E5E&0x03FF-512)*0.25", 23.5),
]
for expr in expressions:
    print(f"Evaluating {expr[0]}...")
    print(f"{expr[1]} = {evaluate_conversion(0, expr[0])}")
