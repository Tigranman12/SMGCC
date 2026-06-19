# Stage 1 — META II / PEG engine

The seed metacompiler for [SMGCC](../README.md). A tiny, dependency-free pattern
matcher: grammar rules recognize input with PEG-style ordered choice +
backtracking, and rules may carry output actions that build an AST.

## Try it

```bash
python3 run.py                 # interactive REPL
python3 run.py "(1 + 2) * 3"   # one-shot
```

Example session:

```
smgcc> 2 + 3 * 4
  ast: (+ 2 (* 3 4))
  =    14
smgcc> :grammar          # show the loaded grammar
```

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

## Files (inputs → outputs)

| File | Input | Output |
|---|---|---|
| `peg.py` | a grammar node + `ParseState` | matched value / `FAIL` (the engine) |
| `grammar.py` | `.peg` text | a `Grammar` of engine nodes (the seed loader) |
| `calc.py` | — | arithmetic actions + evaluator |
| `repl.py` | a line of text | printed AST + result |
| `../grammars/arith.peg` | — | the grammar, as data |

## How it works (the logic)

1. `grammar.py` reads `grammars/arith.peg` into engine nodes (`Lit`, `Seq`,
   `Choice`, `Star`, `Range`, `Act`, …). This is the **bootstrap**: grammars are
   data, not code.
2. `peg.py`'s `match()` walks those nodes over the input, tracking a cursor and
   backtracking on failure. Rule actions (`-> num`, `-> chain`) build the AST.
3. `calc.py` evaluates the AST.

To change the language, edit `arith.peg` — no engine code changes. That is the
META II promise, and the seed on which later stages (real C lexing/parsing) are
built.
