# SMGCC Function Specification — Stage 1

Contract-level reference for every public function and type in the Stage 1 engine.
Format per entry: **signature → returns**, parameters, behavior, errors.

Sentinels (module `smgcc.peg`):
- `FAIL` — a unique object meaning "this node did not match here".
- `SKIP` — a unique object meaning "matched, but produce no value" (whitespace,
  lookahead, missed optionals). Dropped from sequence results.

---

## `smgcc/peg.py` — the matching engine

### `class ParseState(text: str)`
Mutable cursor over the input.
- **Fields:** `text: str` (immutable input), `cursor: int` (current index, starts 0),
  `max_pos: int` (deepest index ever reached — used for error location).
- **Invariant:** `0 <= cursor <= len(text)`.

### Grammar node types (data only, no methods)
Each is a `@dataclass`; together they form the grammar AST consumed by `match`.

| Type | Fields | Meaning |
|---|---|---|
| `Lit` | `value: str` | literal text; skips leading whitespace |
| `Range` | `start: str, end: str` | one char in `[start..end]`; no ws skip |
| `Seq` | `items: list` | A then B then C |
| `Choice` | `items: list` | ordered choice A / B |
| `Star` | `item` | zero or more |
| `Plus` | `item` | one or more |
| `Opt` | `item` | optional |
| `And` | `item` | positive lookahead `&` |
| `Not` | `item` | negative lookahead `!` |
| `Ref` | `name: str` | reference to a named rule |
| `Act` | `item, action: str` | run output action on matched value |
| `Ws` (singleton `WS`) | — | skip whitespace |

### `match(node, st: ParseState, g: Grammar) -> Any`
The core recursive matcher.
- **Parameters:** `node` a grammar node; `st` the parse state (mutated); `g` the
  grammar providing rules + actions.
- **Returns:** on success, the produced value and advances `st.cursor`; on failure,
  the `FAIL` sentinel. `SKIP` may be returned for value-less matches.
- **Per-node contract:**
  - `Lit` → matched string, or `FAIL`. Skips leading whitespace first.
  - `Range` → the single matched char, or `FAIL`.
  - `Ws` → `SKIP` (always succeeds).
  - `Seq` → list of non-`SKIP` child values; on any child `FAIL`, restores cursor
    to the sequence start and returns `FAIL` (full backtrack).
  - `Choice` → value of the first alternative that succeeds; restores cursor before
    each try; `FAIL` if none match.
  - `Star`/`Plus` → list of values; stop on `FAIL` or zero-width match (loop guard).
    `Plus` returns `FAIL` if the first match fails.
  - `Opt` → matched value, or `SKIP` if absent (never `FAIL`).
  - `And` → `SKIP` if inner matches else `FAIL`; never consumes.
  - `Not` → `SKIP` if inner fails else `FAIL`; never consumes.
  - `Ref` → result of matching the referenced rule.
  - `Act` → `g.actions[name](value)` applied to the matched value; `FAIL` if inner fails.
- **Raises:** `KeyError` for an unknown rule (`Ref`) or unknown action (`Act`);
  `TypeError` for an unrecognized node.
- **Side effects:** mutates `st.cursor` and `st.max_pos`.

### `class ParseError(text: str, pos: int)`
Exception with a human-readable line + caret pointer.
- **Fields:** `pos: int` (failure index). Message shows the offending line and a
  `^` under column `pos`.

### `class Grammar(rules: dict, actions: dict, start: str)`
A loaded grammar.
- **Fields:** `rules: {name: node}`, `actions: {name: callable}`, `start: str`.
- **`parse(text: str, rule: str = None) -> Any`**
  - Parses `text` using `rule` (default `start`). Requires the **entire** input to
    be consumed (trailing whitespace allowed).
  - **Returns:** the start rule's produced value.
  - **Raises:** `ParseError` if matching fails or input is not fully consumed (the
    caret points at `st.max_pos`).

---

## `smgcc/grammar.py` — the seed grammar loader

### `load(text: str, actions: dict) -> Grammar`
Parse a `.peg` grammar (one rule per line) into a `Grammar`.
- **Parameters:** `text` grammar source; `actions` maps action names used by `->`
  to host callables `value -> value`.
- **Returns:** a `Grammar`; the **first** rule is the start rule.
- **Behavior:** strips `#` comments and blank lines; each line is `name = alternation`.
- **Raises:** `SyntaxError` on malformed grammar (bad rule, unterminated literal,
  empty sequence, missing `=`/`)`/`]`, no rules).

### `class _Reader(line: str)` *(internal)*
Hand-written recursive-descent reader for one rule line. Methods mirror the DSL
grammar: `rule → alternation → action_seq → sequence → prefixed → postfix →
primary`, plus `_literal`, `_range`, `ident`. Not part of the public API.

---

## `smgcc/calc.py` — arithmetic playground

### Output actions (registered in `ACTIONS`)
- `_num(v) -> ('num', int)` — `v == [[<digit chars>]]`; joins digits to an int.
- `_chain(v) -> ast` — `v == [first, [[op, rhs], ...]]`; folds left-associatively
  into nested `(op, left, right)` tuples.
- `_paren(v) -> ast` — `v == ['(', expr, ')']`; returns the inner `expr`.
- `ACTIONS: dict` — `{"num": _num, "chain": _chain, "paren": _paren}`.

### `load_calc() -> Grammar`
Reads `grammars/arith.peg` from disk and returns a runnable `Grammar` wired to
`ACTIONS`. **Raises:** `OSError` if the grammar file is missing.

### `grammar_text() -> str`
Returns the raw contents of `grammars/arith.peg`.

### `evaluate(node) -> int`
Walks the AST and computes its integer value.
- **AST:** `('num', n)` or `(op, left, right)` with `op` in `+ - * /`.
- **Returns:** the computed `int` (division truncates toward zero, C-style).
- **Raises:** `ZeroDivisionError` on `/ 0`; `ValueError` on an unknown operator.

### `show_ast(node) -> str`
Renders the AST as an S-expression, e.g. `(+ 1 (* 2 3))`. Pure, no errors.

---

## `smgcc/repl.py` — the playground UI

### `run(argv: list) -> int`
Entry point. With extra args, evaluates `" ".join(argv[1:])` once; otherwise runs
the interactive REPL (`:grammar`, `:help`, `:q`). **Returns:** process exit status
(`0` ok, `1` parse error in one-shot mode).

### `_eval_line(g: Grammar, line: str) -> int` *(internal)*
Parses + evaluates one line, printing the AST and result, or a `ParseError`.
**Returns:** `0` on success, `1` on parse error.

---

## Invariants & guarantees (hold across the engine)
1. **Backtracking is total:** a failed `Seq`/`Choice`/`Star` leaves `cursor` where it
   began that attempt — no partial consumption leaks out.
2. **No left recursion:** grammars must use repetition instead (enforced by
   convention, see `arith.peg`); direct left recursion would not terminate.
3. **Whitespace:** only `Lit` and `Ws` skip whitespace; `Range` is contiguous, so
   tokens like numbers never absorb internal spaces.
4. **Full-input rule:** `Grammar.parse` rejects trailing junk; partial parses are errors.
