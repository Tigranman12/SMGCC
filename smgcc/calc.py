"""Arithmetic playground built on the META II/PEG engine.

The grammar lives in ../grammars/arith.peg. Here we only supply the *output
actions* (which build a small AST) and an evaluator that walks that AST.

AST shape:
    ('num', 41)                 a number
    ('+', left, right)          a binary operation  (+ - * /)
"""
import os
from .grammar import load

_HERE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR_PATH = os.path.join(_HERE, os.pardir, "grammars", "arith.peg")


# --- output actions (called by rules via `-> name`) -------------------------
def _num(v):
    # v == [ [<digit chars>] ]  ->  ('num', int)
    return ("num", int("".join(v[0])))


def _chain(v):
    # v == [ first, [ [op, rhs], ... ] ]  ->  left-associative AST
    node = v[0]
    for op, rhs in v[1]:
        node = (op, node, rhs)
    return node


def _paren(v):
    # v == [ '(', <expr>, ')' ]  ->  inner expr
    return v[1]


ACTIONS = {"num": _num, "chain": _chain, "paren": _paren}


def load_calc():
    """Load the arithmetic grammar from disk into a runnable Grammar."""
    with open(GRAMMAR_PATH, encoding="utf-8") as f:
        return load(f.read(), ACTIONS)


def grammar_text() -> str:
    with open(GRAMMAR_PATH, encoding="utf-8") as f:
        return f.read()


def evaluate(node):
    """Walk the AST and compute its value (C-style integer arithmetic)."""
    if node[0] == "num":
        return node[1]
    op, a, b = node
    a, b = evaluate(a), evaluate(b)
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ZeroDivisionError("division by zero")
        return int(a / b)          # truncate toward zero, like C
    raise ValueError(f"unknown operator: {op!r}")


def show_ast(node) -> str:
    """Render the AST as a readable S-expression."""
    if node[0] == "num":
        return str(node[1])
    op, a, b = node
    return f"({op} {show_ast(a)} {show_ast(b)})"
