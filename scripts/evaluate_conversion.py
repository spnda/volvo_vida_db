import ast
import operator as op

from read_csv import get_csv_df

operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.BitAnd: op.and_,
    ast.BitXor: op.xor,
    ast.USub: op.neg
}

def evaluate_ast(node: ast.expr, x: float):
    """
    Evalutes an AST tree with only what the conversions values from VIDA use.
    For the most part, this is just basic arithmetic with some bitwise operations and only a single variable, x.
    """
    if isinstance(node, ast.Num): # number
        return node.n
    elif isinstance(node, ast.Name): # variable (x)
        return x
    elif isinstance(node, ast.BinOp): # binary operation (a + b)
        return operators[type(node.op)](evaluate_ast(node.left, x), evaluate_ast(node.right, x))
    else:
        raise TypeError(node)

def evaluate_conversion(x: int, conversion: str) -> float:
    return evaluate_ast(ast.parse(conversion, mode='eval').body, x)
