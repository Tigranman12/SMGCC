"""Stage 1 test suite. Run: python3 -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from smgcc.peg import (ParseState, match, Lit, Range, Seq, Choice, Star, Plus,
                       Opt, And, Not, Grammar, ParseError, FAIL)
from smgcc.grammar import load
from smgcc.calc import load_calc, evaluate, ACTIONS, show_ast

_G = Grammar({}, {}, None)  # empty grammar for primitive-node tests


def _try(node, text):
    st = ParseState(text)
    r = match(node, st, _G)
    return r, st


class EngineTests(unittest.TestCase):
    def test_literal_match(self):
        r, st = _try(Lit("if"), "if")
        self.assertEqual(r, "if")
        self.assertEqual(st.cursor, 2)

    def test_literal_skips_leading_ws(self):
        r, _ = _try(Lit("if"), "   if")
        self.assertEqual(r, "if")

    def test_choice_backtracks(self):
        node = Choice([Lit("int"), Lit("void")])
        self.assertEqual(_try(node, "void")[0], "void")

    def test_choice_order_first_wins(self):
        node = Choice([Lit("if"), Lit("iffy")])
        r, st = _try(node, "iffy")
        self.assertEqual(r, "if")          # classic PEG pitfall: stops at 'if'
        self.assertEqual(st.cursor, 2)

    def test_negative_lookahead_rejects_keyword_in_identifier(self):
        # 'if' must NOT be followed by a letter -> rejects "iffy"
        kw = Seq([Lit("if"), Not(Range("a", "z"))])
        self.assertIs(_try(kw, "iffy")[0], FAIL)
        self.assertEqual(_try(kw, "if")[0], ["if"])

    def test_repetition(self):
        r, _ = _try(Plus(Range("0", "9")), "412")
        self.assertEqual(r, ["4", "1", "2"])

    def test_optional_miss_does_not_fail(self):
        r, st = _try(Opt(Lit("x")), "y")
        self.assertIsNot(r, FAIL)
        self.assertEqual(st.cursor, 0)


class CalcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_calc()

    def ev(self, s):
        return evaluate(self.g.parse(s))

    def test_number(self):
        self.assertEqual(self.g.parse("  41 ", "number"), ("num", 41))

    def test_addition(self):
        self.assertEqual(self.ev("41 + 1"), 42)

    def test_precedence(self):
        self.assertEqual(self.ev("2 + 3 * 4"), 14)

    def test_parentheses(self):
        self.assertEqual(self.ev("(2 + 3) * 4"), 20)

    def test_left_associative_subtraction(self):
        self.assertEqual(self.ev("20 - 2 - 3"), 15)

    def test_integer_division(self):
        self.assertEqual(self.ev("20 / 3"), 6)

    def test_nested(self):
        self.assertEqual(self.ev("((1+2)*(3+4)) - 1"), 20)

    def test_ast_shape(self):
        self.assertEqual(show_ast(self.g.parse("1+2*3")), "(+ 1 (* 2 3))")

    def test_division_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            self.ev("1 / 0")

    def test_syntax_error_has_position(self):
        with self.assertRaises(ParseError):
            self.g.parse("2 +")
        with self.assertRaises(ParseError):
            self.g.parse("(1 + 2")


class GrammarLoaderTests(unittest.TestCase):
    def test_loads_rules_and_start(self):
        g = load("greeting = 'hi' / 'hello'", {})
        self.assertEqual(g.start, "greeting")
        self.assertEqual(g.parse("hello"), "hello")

    def test_bootstrap_self_describes_alternatives(self):
        # a tiny grammar with an action, loaded entirely from text
        g = load("digit = [0-9] -> id", {"id": lambda v: int(v)})
        self.assertEqual(g.parse("7"), 7)


if __name__ == "__main__":
    unittest.main()
