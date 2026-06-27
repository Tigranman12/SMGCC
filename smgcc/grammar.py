"""Seed grammar loader — reads a `.peg` grammar file into engine nodes.

This hand-written recursive-descent reader is the *seed metacompiler*: the one
parser we write by hand so that every grammar after it can be described in text
instead of code. Supported DSL (one rule per line):

    name = alternation

    alternation : seq ('/' seq)*          ordered choice
    seq         : prefixed+               A B C  (space separated)
    prefixed    : ('!' | '&')? postfix    lookahead
    postfix     : primary ('*'|'+'|'?')?  repetition
    primary     : '(' alternation ')'
                | "'" literal "'"          literal text
                | '[' a '-' b ']'          char range
                | name                     rule reference
                | '_'                      whitespace skip
    action      : '-> name' after a seq   attach output action

Comments start with '#'. Blank lines are ignored.
"""
from .peg import (Lit, Range, Seq, Choice, Star, Plus, Opt, And, Not, Ref, Act,
                  WS, ANY, Grammar)

_IDENT_START = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_IDENT_CHARS = _IDENT_START + "0123456789"


class _Reader:
    def __init__(self, line: str):
        self.s = line
        self.i = 0
        self.n = len(line)

    # -- low-level helpers ---------------------------------------------------
    def ws(self):
        while self.i < self.n and self.s[self.i] in " \t":
            self.i += 1

    def peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def at(self, k: int) -> str:
        j = self.i + k
        return self.s[j] if j < self.n else ""

    def error(self, msg: str):
        raise SyntaxError(f"grammar: {msg} in {self.s!r} at col {self.i + 1}")

    def ident(self) -> str:
        self.ws()
        if self.peek() not in _IDENT_START:
            self.error("expected name")
        start = self.i
        while self.i < self.n and self.s[self.i] in _IDENT_CHARS:
            self.i += 1
        return self.s[start:self.i]

    # -- grammar grammar -----------------------------------------------------
    def rule(self):
        name = self.ident()
        self.ws()
        if self.peek() != "=":
            self.error("expected '='")
        self.i += 1
        node = self.alternation()
        self.ws()
        if self.i != self.n:
            self.error("trailing characters")
        return name, node

    def alternation(self):
        alts = [self.action_seq()]
        self.ws()
        while self.peek() == "/":
            self.i += 1
            alts.append(self.action_seq())
            self.ws()
        return alts[0] if len(alts) == 1 else Choice(alts)

    def action_seq(self):
        node = self.sequence()
        self.ws()
        if self.peek() == "-" and self.at(1) == ">":
            self.i += 2
            name = self.ident()
            return Act(node, name)
        return node

    def _at_seq_end(self) -> bool:
        self.ws()
        c = self.peek()
        if c == "" or c in "/)":
            return True
        if c == "-" and self.at(1) == ">":
            return True
        return False

    def sequence(self):
        items = []
        while not self._at_seq_end():
            items.append(self.prefixed())
        if not items:
            self.error("empty sequence")
        return items[0] if len(items) == 1 else Seq(items)

    def prefixed(self):
        self.ws()
        c = self.peek()
        if c == "!":
            self.i += 1
            return Not(self.postfix())
        if c == "&":
            self.i += 1
            return And(self.postfix())
        return self.postfix()

    def postfix(self):
        node = self.primary()
        c = self.peek()
        if c == "*":
            self.i += 1
            return Star(node)
        if c == "+":
            self.i += 1
            return Plus(node)
        if c == "?":
            self.i += 1
            return Opt(node)
        return node

    def primary(self):
        self.ws()
        c = self.peek()
        if c == "(":
            self.i += 1
            node = self.alternation()
            self.ws()
            if self.peek() != ")":
                self.error("expected ')'")
            self.i += 1
            return node
        if c == "'":
            return self._literal()
        if c == "[":
            return self._range()
        if c == ".":
            self.i += 1
            return ANY
        if c in _IDENT_START:
            name = self.ident()
            return WS if name == "_" else Ref(name)
        self.error("unexpected character")

    def _literal(self):
        self.i += 1  # opening quote
        chars = []
        while self.i < self.n and self.s[self.i] != "'":
            if self.s[self.i] == "\\" and self.i + 1 < self.n:
                esc = self.s[self.i + 1]
                if esc == "n": chars.append("\n")
                elif esc == "t": chars.append("\t")
                elif esc == "r": chars.append("\r")
                elif esc == "\\": chars.append("\\")
                elif esc == "'": chars.append("'")
                else: chars.append(esc)
                self.i += 2
            else:
                chars.append(self.s[self.i])
                self.i += 1
        if self.peek() != "'":
            self.error("unterminated literal")
        text = "".join(chars)
        self.i += 1  # closing quote
        if not text:
            self.error("empty literal")
        return Lit(text)

    def _range(self):
        self.i += 1  # '['
        lo = self.peek()
        if not lo:
            self.error("bad range")
        self.i += 1
        if self.peek() != "-":
            self.error("expected '-' in range")
        self.i += 1
        hi = self.peek()
        if not hi:
            self.error("bad range")
        self.i += 1
        if self.peek() != "]":
            self.error("expected ']'")
        self.i += 1
        return Range(lo, hi)


def load(text: str, actions: dict) -> Grammar:
    """Parse grammar `text` into a Grammar. The first rule is the start rule."""
    rules = {}
    start = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        name, node = _Reader(line).rule()
        rules[name] = node
        if start is None:
            start = name
    if start is None:
        raise SyntaxError("grammar: no rules")
    return Grammar(rules, actions, start)
