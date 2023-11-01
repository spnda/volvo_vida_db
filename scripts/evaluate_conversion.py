#!/usr/bin/env python3

import operator as op
import re
from math import log
import sys

operators = {
    '+': op.add,
    '-': op.sub,
    '*': op.mul,
    '/': op.truediv,
    '^': op.pow,
    '&': op.and_,
}

functions = {
    'ln': log,
}

class Node(): pass
class Variable(Node): pass
class Value(Node):
    value: int | float
    def __init__(self, value: int | float):
        self.value = value
class BinaryOp(Node):
    left: Node
    right: Node
    op: str
    def __init__(self, left: Node, right: Node, op: str):
        self.left = left
        self.right = right
        self.op = op
class Function(Node):
    func: str
    arg: Node
    def __init__(self, arg: Node, func: str):
        self.arg = arg
        self.func = func

def evaluate_ast(node: Node, x: float):
    """
    Evalutes an AST tree with only what the conversions values from VIDA use.
    For the most part, this is just basic arithmetic with some bitwise operations and only a single variable, x.
    """
    if isinstance(node, Value):
        return node.value
    elif isinstance(node, Variable):
        return x
    elif isinstance(node, Function):
        return functions[node.func](evaluate_ast(node.arg, x))
    elif isinstance(node, BinaryOp): # binary operation (a + b)
        return operators[node.op](evaluate_ast(node.left, x), evaluate_ast(node.right, x))
    else:
        print(node)
        raise TypeError(node)

def get_op_precedence(op: str) -> int:
    if op == '+' or op == '-':
        return 0
    elif op == '*' or op == '/':
        return 1
    elif op == '^':
        return 2
    elif op == '&':
        return 3
    raise ValueError

def is_number(expr: str) -> bool:
    # check if float/int, hex, or binary.
    return bool(re.fullmatch(r'^[+-]?([0-9]*[.])?[0-9]+$', expr)) or bool(re.fullmatch(r'(0x)[0-9A-Fa-f]+', expr)) or bool(re.fullmatch(r'(0b)[0-1]+', expr))

def parse_number(expr: str) -> int | float:
    if len(expr) <= 2:
        return int(expr)
    if expr.startswith('0x'):
        return int(expr[2:], base=16)
    elif expr.startswith('0b'):
        return int(expr[2:], base=2)
    elif '.' in expr:
        return float(expr)
    else:
        return int(expr)

def parse_conversion(expr: str) -> Node:
    # Remove unnecessary whitespaces
    expr = expr.strip()

    if expr.lower() == 'x':
        return Variable()
    
    if is_number(expr):
        return Value(value=parse_number(expr))
    
    if '(' in expr:
        bracket_idx = expr.index('(')
        if expr[:bracket_idx].isalpha() and expr.count('(') == expr.count(')') and expr[-1] == ')':
            # Function call
            return Function(arg=parse_conversion(expr[bracket_idx+1:-1]), func=expr[:bracket_idx])
    
    # Find the lowest operator in the expression and look for the first one.
    i = 0
    lowest_operator = None
    while i < len(expr):
        ch = expr[i]
        if expr[i] == '(':
            # Skip to the end of the brackets
            brackets = 0
            while i < len(expr):
                if expr[i] == '(':
                    brackets += 1
                elif expr[i] == ')':
                    brackets -= 1
                i += 1
                if brackets == 0:
                    break
            
            if i == len(expr):
                if lowest_operator is None:
                    # We've reached the end of the expression and the brackets seem to cover the entire expression. Remove them.
                    return parse_conversion(expr[1:-1])
                else:
                    break
            ch = expr[i]
        
        if ch in operators:
            if (ch == '-' and i == 0) or (ch == '-' and (expr[i-1] in operators or expr[i-1] == 'E')):
                # This is a unary minus operator either at the beginning of an expression, right after another operator,
                # or within exponential notation. We'll just skip it so that it will process as a single expression.
                pass
            elif lowest_operator is None or get_op_precedence(ch) < get_op_precedence(lowest_operator[0]):
                lowest_operator = (ch, i)
        
            # Early return when lowest possible found.
            if get_op_precedence(lowest_operator[0]) == 0:
                break

        i += 1

    if lowest_operator is None:
        # This could only happen when there's only a single value, such as "5". This should be caught by is_number.
        raise ValueError()

    left = parse_conversion(expr[:lowest_operator[1]])
    right = parse_conversion(expr[lowest_operator[1]+1:])
    return BinaryOp(left=left, op=lowest_operator[0], right=right)

def evaluate_conversion(x: int, conversion: str) -> float:
    return evaluate_ast(parse_conversion(conversion), x)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: evaluate_conversion.py <integer value for x> <expression>')
    else:
        print(evaluate_conversion(int(sys.argv[1]), sys.argv[2]))
    