"""COLA reader — source text to an s-expression AST, via the SMGCC PEG engine.

AST node shapes (tuples, tag-first):
    ('int', n)            integer literal
    ('str', s)            string literal
    ('sym', name)         symbol / identifier / operator
    ('list', [elem, ...]) a parenthesised list
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from smgcc.grammar import load

_HERE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR_PATH = os.path.join(_HERE, os.pardir, "grammars", "cola.peg")


def _program(v):
    return ("program", v)

def _list(v):
    # ['(', [elems], ')']
    return ("list", v[1])

def _num(v):
    return ("int", int("".join(v[0])))

def _str(v):
    # ['"', [chars], '"']
    return ("str", "".join(v[1]))

def _char(v):
    return v[0]

def _sym(v):
    return ("sym", "".join(v[0]))


ACTIONS = {"program": _program, "list": _list, "num": _num, "str": _str,
           "char": _char, "sym": _sym}

_GRAMMAR = None


def _grammar():
    global _GRAMMAR
    if _GRAMMAR is None:
        with open(GRAMMAR_PATH, encoding="utf-8") as f:
            _GRAMMAR = load(f.read(), ACTIONS)
    return _GRAMMAR


def read(src: str):
    """Parse COLA source into a list of top-level forms."""
    return _grammar().parse(src)[1]
