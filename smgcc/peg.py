"""SMGCC Stage 1 — META II / PEG matching engine.

A tiny, dependency-free pattern matcher. Grammar rules recognize input with
PEG-style ordered choice + backtracking, and any rule may carry an output
action that builds an AST value. See ../EXPL_STAGE.md for the theory.

The whole engine is one recursive function, `match`, over a handful of node
types. Nothing is hidden — you can trace every parse by hand.
"""
from dataclasses import dataclass
from typing import Any, List

# Two sentinels carried through the matcher:
FAIL = object()   # a match that did not succeed
SKIP = object()   # a matched value to drop from a sequence (whitespace, etc.)


class ParseState:
    """Tracks where we are in the input. `max_pos` is the deepest index ever
    reached — that's almost always where a real syntax error lives."""
    __slots__ = ("text", "cursor", "max_pos")

    def __init__(self, text: str):
        self.text = text
        self.cursor = 0
        self.max_pos = 0


# --- grammar node types -----------------------------------------------------
@dataclass
class Lit:
    """A literal string, e.g. 'if'. Skips leading whitespace before matching."""
    value: str

@dataclass
class Range:
    """A character class, e.g. [a-z]. Does NOT skip whitespace (stays a token)."""
    start: str
    end: str

@dataclass
class Seq:
    """A then B then C. Any failure backtracks the whole sequence."""
    items: List[Any]

@dataclass
class Choice:
    """Ordered choice A / B. First alternative that succeeds wins."""
    items: List[Any]

@dataclass
class Star:
    """Zero or more (greedy)."""
    item: Any

@dataclass
class Plus:
    """One or more."""
    item: Any

@dataclass
class Opt:
    """Optional (zero or one)."""
    item: Any

@dataclass
class And:
    """Positive lookahead &x — matches without consuming."""
    item: Any

@dataclass
class Not:
    """Negative lookahead !x — succeeds only if x does NOT match."""
    item: Any

@dataclass
class Ref:
    """Reference to another named rule."""
    name: str

@dataclass
class Act:
    """Attach an output action: run actions[name] on the matched value."""
    item: Any
    action: str

class Ws:
    """Skip whitespace, always succeeds, produces nothing."""
WS = Ws()


_WHITESPACE = " \t\r\n"


def _skip_ws(st: ParseState) -> None:
    n = len(st.text)
    while st.cursor < n and st.text[st.cursor] in _WHITESPACE:
        st.cursor += 1


def _track(st: ParseState) -> None:
    if st.cursor > st.max_pos:
        st.max_pos = st.cursor


def match(node, st: ParseState, g) -> Any:
    """Try to match `node` at the current cursor. Returns the produced value on
    success (advancing the cursor) or FAIL (callers restore the cursor)."""
    t = type(node)

    if t is Lit:
        _skip_ws(st)
        v = node.value
        if st.text.startswith(v, st.cursor):
            st.cursor += len(v)
            _track(st)
            return v
        return FAIL

    if t is Range:
        if st.cursor < len(st.text) and node.start <= st.text[st.cursor] <= node.end:
            ch = st.text[st.cursor]
            st.cursor += 1
            _track(st)
            return ch
        return FAIL

    if t is Ws:
        _skip_ws(st)
        return SKIP

    if t is Seq:
        save = st.cursor
        out = []
        for item in node.items:
            r = match(item, st, g)
            if r is FAIL:
                st.cursor = save           # backtrack the whole sequence
                return FAIL
            if r is not SKIP:
                out.append(r)
        return out

    if t is Choice:
        for item in node.items:
            save = st.cursor
            r = match(item, st, g)
            if r is not FAIL:
                return r                   # first success wins
            st.cursor = save               # backtrack and try the next
        return FAIL

    if t is Star:
        out = []
        while True:
            save = st.cursor
            r = match(node.item, st, g)
            if r is FAIL or st.cursor == save:   # stop on fail or zero-width
                st.cursor = save
                break
            if r is not SKIP:
                out.append(r)
        return out

    if t is Plus:
        first = match(node.item, st, g)
        if first is FAIL:
            return FAIL
        out = [] if first is SKIP else [first]
        while True:
            save = st.cursor
            r = match(node.item, st, g)
            if r is FAIL or st.cursor == save:
                st.cursor = save
                break
            if r is not SKIP:
                out.append(r)
        return out

    if t is Opt:
        save = st.cursor
        r = match(node.item, st, g)
        if r is FAIL:
            st.cursor = save
            return SKIP
        return r

    if t is And:
        save = st.cursor
        r = match(node.item, st, g)
        st.cursor = save                   # lookahead never consumes
        return SKIP if r is not FAIL else FAIL

    if t is Not:
        save = st.cursor
        r = match(node.item, st, g)
        st.cursor = save
        return FAIL if r is not FAIL else SKIP

    if t is Ref:
        target = g.rules.get(node.name)
        if target is None:
            raise KeyError(f"unknown rule: {node.name!r}")
        return match(target, st, g)

    if t is Act:
        r = match(node.item, st, g)
        if r is FAIL:
            return FAIL
        fn = g.actions.get(node.action)
        if fn is None:
            raise KeyError(f"unknown action: {node.action!r}")
        return fn(r)

    raise TypeError(f"not a grammar node: {node!r}")


class ParseError(Exception):
    """Carries a line/caret pointer to the failure position."""
    def __init__(self, text: str, pos: int):
        line_start = text.rfind("\n", 0, pos) + 1
        line_end = text.find("\n", pos)
        if line_end < 0:
            line_end = len(text)
        line = text[line_start:line_end]
        col = pos - line_start
        msg = f"parse error at column {col + 1}:\n  {line}\n  {' ' * col}^"
        super().__init__(msg)
        self.pos = pos


class Grammar:
    """A set of named rules plus the host-language actions they can call."""
    def __init__(self, rules: dict, actions: dict, start: str):
        self.rules = rules
        self.actions = actions
        self.start = start

    def parse(self, text: str, rule: str = None) -> Any:
        st = ParseState(text)
        node = self.rules[rule or self.start]
        result = match(node, st, self)
        _skip_ws(st)
        if result is FAIL or st.cursor != len(text):
            raise ParseError(text, st.max_pos)
        return result
