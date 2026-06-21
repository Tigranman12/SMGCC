"""C-subset grammar actions — Stage 2.

The grammar lives in ../grammars/c.peg. Here we only provide the output actions
that build the AST. AST node shapes (tuples, tag-first):

    ('program', [func, ...])
    ('func', name, [param, ...], block)
        param is a string (int) or ('*', name) (pointer)
    ('block', [stmt, ...])
    ('decl', name, init_expr_or_None)
    ('ptrdecl', name, init_expr_or_None)
    ('ret', expr)
    ('if', cond, then_stmt, else_stmt_or_None)
    ('while', cond, body_stmt)
    ('exprstmt', expr)
    ('assign', target, expr)
    ('bin', op, left, right)
    ('un', op, expr)    # op is '-', '!', '*', or '&'
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

def _ptrparam(v):
    # ['*', name]  (kw_int dropped) — pointer parameter
    return ("*", v[1])

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

def _dowhiles(v):
    # [body, '(', cond, ')', ';']   (kw_do and kw_while dropped)
    return ("do_while", v[0], v[2])

def _switchs(v):
    cases = v[4]
    default = None
    if len(v) > 6 and v[5] is not SKIP:
        default = v[5]
    return ("switch", v[1], cases, default)

def _case(v):
    return ("case", v[0], v[2])

def _default(v):
    return ("default", v[1])

def _decl(v):
    # [name, ('=' expr)?, ';']
    init = v[1][1] if len(v) == 3 else None
    return ("decl", v[0], init)

def _ptrdecl(v):
    # ['*', name, ('=' expr)?, ';']  (kw_int dropped)
    init = v[2][1] if len(v) == 4 else None
    return ("ptrdecl", v[1], init)

def _arraydecl(v):
    # [name, '[', expr, ']', ';']  (kw_int dropped)
    return ("arraydecl", v[0], v[2])

def _exprstmt(v):
    return ("exprstmt", v[0])

def _assign(v):
    # [dotassign_result, '=', expr]
    target = v[0]
    if isinstance(target, list):
        # dotassign result: [name, [['.', member], ...]]
        if len(target) == 1:
            target = ("var", target[0])
        else:
            obj = target[0]
            for pair in target[1]:
                obj = ("member", obj, pair[1])
    return ("assign", target, v[2])

def _chain(v):
    node = v[0]
    for op, rhs in v[1]:
        node = ("bin", op, node, rhs)
    return node

def _logor(v):
    node = v[0]
    for pair in v[1]:
        node = ("logor", node, pair[1])
    return node

def _logand(v):
    node = v[0]
    for pair in v[1]:
        node = ("logand", node, pair[1])
    return node

def _enumdecl(v):
    # anonymous: ['{', [vals], '}', ';']   (kw_enum and ident? dropped)
    # named:    [name, '{', [vals], '}', ';']
    if v[0] == '{':
        name = None
        vals = v[1]
    else:
        name = v[0]
        vals = v[2]
    return ("enum", name, vals)

def _enumval(v):
    # [name] or [name, ['=', expr]]
    name = v[0]
    if len(v) > 1 and v[1] is not SKIP:
        val = v[1][1]  # extract expr from ['=', expr]
    else:
        val = None
    return ("enumval", name, val)

def _enumvals(v):
    # [first_val, [[',', val], ...], (',')]
    vals = [v[0]]
    for pair in v[1]:
        vals.append(pair[1])
    return vals

def _structdecl(v):
    # [name, '{', [members], '}']
    return ("structdecl", v[0], v[2])

def _structmember(v):
    # [name]  (kw_int dropped)
    return v[0]

def _structdecl_s(v):
    # [struct_kw, type_name, var_name]  -> ('struct_var', type_name, var_name)
    return ("struct_var", v[0], v[1])

def _dotvar(v):
    # [name, [['.', member], ...]]
    if len(v) == 1:
        return ("var", v[0])
    obj = v[0]
    for pair in v[1]:
        obj = ("member", obj, pair[1])
    if isinstance(obj, str):
        return ("var", obj)
    return obj

def _dereflvalue(v):
    # ['*', unary_result] — construct dereference node for assignment target
    return ("un", "*", v[1])

def _subscript(v):
    # [array, '[', index, ']'] — array subscript access
    return ("subscript", v[0], v[2])

def _foropt(v):
    # expr? : present -> the expr; absent -> SKIP -> None
    return None if v is SKIP else v

def _fordecl(v):
    # [name, '=', expr]   (kw_int dropped)
    return ("decl", v[0], v[2])

def _fors(v):
    # ['(', init, ';', test, ';', step, ')', body]
    init, test, step, body = v[1], v[3], v[5], v[7]
    if init is None:
        init_stmt = None
    elif isinstance(init, tuple) and init[0] == "decl":
        init_stmt = init
    else:
        init_stmt = ("exprstmt", init)
    return ("for", init_stmt, test, step, body)

def _breaks(v):
    return ("break",)

def _continues(v):
    return ("continue",)

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
    "whiles": _whiles, "dowhiles": _dowhiles, "switchs": _switchs,
    "case": _case, "default": _default, "decl": _decl, "exprstmt": _exprstmt,
    "assign": _assign, "chain": _chain, "unary": _unary, "call": _call,
    "args": _args, "var": _var, "paren": _paren, "num": _num, "ident": _ident,
    "skip": _skip, "logor": _logor, "logand": _logand, "opt": _foropt,
    "fordecl": _fordecl, "fors": _fors, "breaks": _breaks, "continues": _continues,
    "enumdecl": _enumdecl, "enumval": _enumval, "enumvals": _enumvals,
    "structdecl": _structdecl, "structmember": _structmember,
    "structdecl_s": _structdecl_s, "dotvar": _dotvar,
    "ptrdecl": _ptrdecl, "dereflvalue": _dereflvalue,
    "ptrparam": _ptrparam, "arraydecl": _arraydecl,
    "subscript": _subscript,
}


def load_c():
    """Load the C-subset grammar from disk into a runnable Grammar."""
    with open(GRAMMAR_PATH, encoding="utf-8") as f:
        return load(f.read(), ACTIONS)
