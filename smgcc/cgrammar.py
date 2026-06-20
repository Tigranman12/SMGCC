"""C-subset grammar actions — Stage 2.

The grammar lives in ../grammars/c.peg. Here we only provide the output actions
that build the AST. AST node shapes (tuples, tag-first):

    ('program', [func, ...])
    ('func', name, [param_name, ...], block)
    ('block', [stmt, ...])
    ('decl', name, init_expr_or_None)
    ('ret', expr)
    ('if', cond, then_stmt, else_stmt_or_None)
    ('while', cond, body_stmt)
    ('exprstmt', expr)
    ('assign', name, expr)
    ('bin', op, left, right)
    ('un', op, expr)
    ('call', name, [arg_expr, ...])
    ('var', name)
    ('num', int)
"""
import os
from .grammar import load
from .peg import SKIP

_HERE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR_PATH = os.path.join(_HERE, os.pardir, "grammars", "c.peg")


def _program(v):
    return ("program", v)

def _func(v):
    # [name, '(', params, ')', block]   (kw_int dropped by -> skip)
    return ("func", v[0], v[2], v[4])

def _params(v):
    if v is SKIP:
        return []
    return [v[0]] + [pair[1] for pair in v[1]]

def _param(v):
    return v[0]

def _block(v):
    # ['{', [stmts], '}']
    return ("block", v[1])

def _ret(v):
    return ("ret", v[0])

def _ifs(v):
    # ['(', cond, ')', then, (else?)]
    els = v[4] if len(v) > 4 else None
    return ("if", v[1], v[3], els)

def _elses(v):
    return v[0]

def _whiles(v):
    return ("while", v[1], v[3])

def _decl(v):
    # [name, ('=' expr)?, ';']
    init = v[1][1] if len(v) == 3 else None
    return ("decl", v[0], init)

def _exprstmt(v):
    return ("exprstmt", v[0])

def _assign(v):
    # [name, '=', expr]   (the !'=' lookahead is dropped)
    return ("assign", v[0], v[2])

def _chain(v):
    # [first, [[op, rhs], ...]]  ->  left-associative binary tree
    node = v[0]
    for op, rhs in v[1]:
        node = ("bin", op, node, rhs)
    return node

def _unary(v):
    return ("un", v[0], v[1])

def _call(v):
    # [name, '(', args, ')']
    return ("call", v[0], v[2])

def _args(v):
    if v is SKIP:
        return []
    return [v[0]] + [pair[1] for pair in v[1]]

def _var(v):
    return ("var", v)

def _paren(v):
    return v[1]

def _num(v):
    return ("num", int("".join(v[0])))

def _ident(v):
    # [first_char, [rest_chars]]
    return v[0] + "".join(v[1])

def _skip(v):
    return SKIP


ACTIONS = {
    "program": _program, "func": _func, "params": _params, "param": _param,
    "block": _block, "ret": _ret, "ifs": _ifs, "elses": _elses,
    "whiles": _whiles, "decl": _decl, "exprstmt": _exprstmt, "assign": _assign,
    "chain": _chain, "unary": _unary, "call": _call, "args": _args,
    "var": _var, "paren": _paren, "num": _num, "ident": _ident, "skip": _skip,
}


def load_c():
    """Load the C-subset grammar from disk into a runnable Grammar."""
    with open(GRAMMAR_PATH, encoding="utf-8") as f:
        return load(f.read(), ACTIONS)
