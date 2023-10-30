from read_csv import t155
from evaluate_conversion import evaluate_conversion

# Small script to test if evaluate_conversion.py covers all cases in the VIDA db
for index, row in t155.iterrows():
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
        print(f"Artihmetic issue. Likely just invalid input data.")
    except SyntaxError:
        print(f"Failed to parse {expression}")
    except TypeError as type_error:
        print(f"Failed to run AST of {expression}: {type_error}")
