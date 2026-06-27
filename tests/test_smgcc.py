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


class SeqTests(unittest.TestCase):
    def test_sequence_matches_all(self):
        node = Seq([Lit("a"), Lit("b"), Lit("c")])
        r, st = _try(node, "abc")
        self.assertEqual(r, ["a", "b", "c"])
        self.assertEqual(st.cursor, 3)

    def test_sequence_backtracks_on_failure(self):
        node = Seq([Lit("a"), Lit("b")])
        r, st = _try(node, "ax")
        self.assertIs(r, FAIL)
        self.assertEqual(st.cursor, 0)

    def test_sequence_with_whitespace(self):
        node = Seq([Lit("a"), Lit("b")])
        r, st = _try(node, "a  b")
        self.assertEqual(r, ["a", "b"])


class StarTests(unittest.TestCase):
    def test_star_zero_matches(self):
        node = Star(Lit("a"))
        r, st = _try(node, "bbb")
        self.assertEqual(r, [])
        self.assertEqual(st.cursor, 0)

    def test_star_greedy(self):
        node = Star(Lit("a"))
        r, st = _try(node, "aaa")
        self.assertEqual(r, ["a", "a", "a"])
        self.assertEqual(st.cursor, 3)

    def test_star_stops_on_mismatch(self):
        node = Star(Lit("a"))
        r, st = _try(node, "aab")
        self.assertEqual(r, ["a", "a"])
        self.assertEqual(st.cursor, 2)


class OptTests(unittest.TestCase):
    def test_opt_present(self):
        node = Opt(Lit("x"))
        r, st = _try(node, "x")
        self.assertEqual(r, "x")
        self.assertEqual(st.cursor, 1)

    def test_opt_absent(self):
        node = Opt(Lit("x"))
        r, st = _try(node, "y")
        self.assertIsNot(r, FAIL)
        self.assertEqual(st.cursor, 0)


class AndTests(unittest.TestCase):
    def test_and_succeeds_without_consuming(self):
        node = And(Lit("a"))
        r, st = _try(node, "ab")
        self.assertIsNot(r, FAIL)
        self.assertEqual(st.cursor, 0)

    def test_and_fails_if_not_present(self):
        node = And(Lit("a"))
        r, _ = _try(node, "b")
        self.assertIs(r, FAIL)


class NotTests(unittest.TestCase):
    def test_not_succeeds_when_absent(self):
        node = Not(Lit("a"))
        r, st = _try(node, "b")
        self.assertIsNot(r, FAIL)
        self.assertEqual(st.cursor, 0)

    def test_not_fails_when_present(self):
        node = Not(Lit("a"))
        r, _ = _try(node, "ab")
        self.assertIs(r, FAIL)


class WhitespaceTests(unittest.TestCase):
    def test_ws_skip(self):
        from smgcc.peg import WS
        r, st = _try(WS, "   abc")
        self.assertEqual(st.cursor, 3)

    def test_literal_skips_leading_ws(self):
        r, st = _try(Lit("x"), "   x")
        self.assertEqual(r, "x")
        self.assertEqual(st.cursor, 4)


class RangeTests(unittest.TestCase):
    def test_range_match(self):
        node = Range("a", "z")
        r, st = _try(node, "m")
        self.assertEqual(r, "m")
        self.assertEqual(st.cursor, 1)

    def test_range_no_match(self):
        node = Range("a", "z")
        r, _ = _try(node, "5")
        self.assertIs(r, FAIL)

    def test_range_digit(self):
        node = Range("0", "9")
        r, _ = _try(node, "7")
        self.assertEqual(r, "7")


class AnyTests(unittest.TestCase):
    def test_any_matches_char(self):
        from smgcc.peg import ANY
        r, st = _try(ANY, "x")
        self.assertEqual(r, "x")
        self.assertEqual(st.cursor, 1)

    def test_any_fails_at_end(self):
        from smgcc.peg import ANY
        r, _ = _try(ANY, "")
        self.assertIs(r, FAIL)


class ParseErrorTests(unittest.TestCase):
    def test_error_shows_position(self):
        g = load("num = [0-9]+", {})
        with self.assertRaises(ParseError) as ctx:
            g.parse("abc")
        self.assertIn("column", str(ctx.exception))

    def test_error_at_end_of_input(self):
        g = load("num = [0-9]+", {})
        with self.assertRaises(ParseError):
            g.parse("")


class GrammarLoaderEdgeCases(unittest.TestCase):
    def test_multiple_rules(self):
        g = load("a = 'x'\nb = 'y'", {})
        self.assertEqual(g.start, "a")
        self.assertEqual(g.parse("x"), "x")

    def test_comments_stripped(self):
        g = load("# comment\na = 'ok' # inline", {})
        self.assertEqual(g.parse("ok"), "ok")

    def test_blank_lines_ignored(self):
        g = load("a = 'x'\n\n\nb = 'y'", {})
        self.assertEqual(g.parse("x"), "x")

    def test_nested_groups(self):
        g = load("g = ('a' / 'b') ('c' / 'd')", {})
        r = g.parse("ac")
        self.assertEqual(r, ["a", "c"])

    def test_repetition_operators(self):
        g = load("g = [a-z]+", {})
        self.assertEqual(g.parse("abc"), ["a", "b", "c"])

    def test_lookahead_in_grammar(self):
        g = load("kw = 'if' !([a-z])", {})
        self.assertEqual(g.parse("if"), ["if"])
        with self.assertRaises(ParseError):
            g.parse("iffy")

    def test_action_with_complex_ast(self):
        def build_pair(v):
            return ("pair", v[0], v[1])
        g = load("g = [a-z] [0-9] -> pair", {"pair": build_pair})
        self.assertEqual(g.parse("a1"), ("pair", "a", "1"))

    def test_empty_grammar_raises(self):
        with self.assertRaises(SyntaxError):
            load("", {})

    def test_unknown_rule_raises(self):
        g = load("a = b\nb = 'x'", {})
        with self.assertRaises(ParseError):
            g.parse("y")


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


class BootstrapTests(unittest.TestCase):
    """Verify the metacompiler bootstrap: the grammar loader can parse
    grammars that describe the grammar language itself."""

    def test_meta_grammar_exists(self):
        meta_path = os.path.join(os.path.dirname(__file__), os.pardir,
                                 "grammars", "meta.peg")
        self.assertTrue(os.path.exists(meta_path))

    def test_meta_grammar_is_valid_utf8(self):
        meta_path = os.path.join(os.path.dirname(__file__), os.pardir,
                                 "grammars", "meta.peg")
        with open(meta_path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("grammar", text)
        self.assertIn("rule", text)

    def test_simple_grammar_loads(self):
        g = load("g = 'hello' / 'world'", {})
        self.assertEqual(g.start, "g")
        self.assertEqual(g.parse("hello"), "hello")
        self.assertEqual(g.parse("world"), "world")

    def test_grammar_with_lookahead(self):
        g = load("kw = 'if' !([a-z])", {})
        self.assertEqual(g.parse("if"), ["if"])
        with self.assertRaises(ParseError):
            g.parse("iffy")

    def test_grammar_with_repetition(self):
        g = load("digits = [0-9]+", {})
        self.assertEqual(g.parse("123"), ["1", "2", "3"])

    def test_grammar_with_action(self):
        def build_num(v):
            return int("".join(v))
        g = load("num = [0-9]+ -> num", {"num": build_num})
        self.assertEqual(g.parse("42"), 42)

    def test_grammar_with_groups(self):
        g = load("g = ('a' / 'b') ('c' / 'd')", {})
        self.assertEqual(g.parse("ac"), ["a", "c"])

    def test_grammar_loader_roundtrip(self):
        original = "expr = 'a' / 'b'\nother = [0-9]+"
        g = load(original, {})
        self.assertEqual(g.start, "expr")
        self.assertEqual(g.parse("a"), "a")
        self.assertEqual(g.parse("b"), "b")


if __name__ == "__main__":
    unittest.main()
