#!/usr/bin/env python3

from read_csv import get_csv, DatabaseFile
from evaluate_conversion import evaluate_conversion, evaluate_conversion_from_str

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
    # These are literally the tests from the actual VIDA application found in
    # Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.test.CalculatorTest
    ("(1+2)*3", 9),
    ("10&0xF", 10),
    ("10&0b11001010", 10),
    ("1", 1),
    ("3*(-1)", -3),
    ("3*(-1) + 3", 0),
    ("int(log(3)+ln(3))", 2),
    ("0b0001|0b0010", 3),
    ("(4)-4", 0),
    ("(0.1*100)-1.5", 8.5),

    # Some tests from the data sets
    ("int(1.5)", 2),
    ("10.7&0xF", 10),
    ("(0x0E5E&0x03FF-512)*0.25", 23.5),

    # Operators with the same precedence are evaluated from left to right
    ("10-2-3", 5),
    ("64/4/2", 8),
    ("2^3^2", 64),
    ("-2*3+10", 4),
]
for expr, res in expressions:
    print(f"Evaluating {expr}...")
    print(f"{res} = {evaluate_conversion(0, expr)}")

scale_expressions = [
    # Again, these are literally the tests for the Scaler class in VIDA found in
    # Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.test.ScalerTest
    ("(x*1)", "10", 10.0),
    ("(X*1)", "10", 10.0),
    ("(1+x*1)", "10", 11.0),
    ("(1+x)", "10", 11.0),
    ("x*1 + (x + 2)", "10", 22.0),
    ("x*1 + (x + 2 + x)", "10", 32.0),
    ("(x*1)", "0xFF", 255.0),
    ("(X*1)", "0xFF", 255.0),
    ("(X&0x03FF-512)*0.25", "0x0E5E", 23.5), # lol there's actually a bug in VIDA's unit tests here
]
for scaling, val, res in scale_expressions:
    print(f"Evaluating {scaling} with x={val}")
    print(f"{res} = {evaluate_conversion_from_str(val, scaling)}")
