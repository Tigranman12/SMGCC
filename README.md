# SMGCC — Self-hosting Minimalist C Compiler

> A tiny C compiler, built from scratch, that can eventually **compile its own source code.**

---

## 1. What is this, in plain words?

A **compiler** is a program that translates code humans write (C source) into code a
machine can run (assembly / machine instructions).

SMGCC is a compiler for a subset of **C**, with three goals that shape every decision:

- **Minimal** — as little code as possible. Tiny files, almost no dependencies.
- **Fast** — quick to compile, in the spirit of [TinyCC](https://bellard.org/tcc/).
- **Self-hosting** — the final milestone is feeding SMGCC *its own source code* and
  having it produce a working copy of itself. When that loop closes, the compiler is
  truly independent.

The twist: we do **not** hand-write a giant parser. Instead we build a small
**metacompiler** (a "compiler that builds compilers") based on **META II**. We describe
the language's grammar in a short rules file, and the metacompiler turns those rules into
the actual parser. Want to change the language? Edit the grammar file, not thousands of
lines of code.

---

## 2. Why build it this way?

| Traditional compiler | SMGCC |
|---|---|
| Hand-written lexer (~300 lines) | Grammar rules in a small file |
| Hand-written parser (~2000 lines) | Parser **generated** from the grammar |
| Painful to change the language | Change a rule, regenerate |
| Hard to ever self-host | Self-hosting is the built-in goal |

This idea comes from **META II** (Val Schorre, 1964) and the **VPRI STEPS** work
(Alan Kay) — the principle that a small, well-chosen language can describe much bigger
systems, including itself.

---

## 3. Architecture

SMGCC is a classic compiler pipeline. Source goes in the top, runnable code comes out the
bottom, and each box does one well-defined job:

```
   ┌──────────────┐
   │  C Source    │   e.g.  int main() { return 41 + 1; }
   └──────┬───────┘
          │
          ▼
   ┌────────────────────────────┐
   │ META II Parser (Stage 1+2) │  grammar rules → tokens → syntax
   └──────┬─────────────────────┘
          ▼
   ┌──────────────┐
   │  AST         │   Abstract Syntax Tree (the program as a structured tree)
   └──────┬───────┘
          ▼
   ┌────────────────────────────┐
   │ Semantic Analyzer (Stage 3)│  types, scopes, symbol tables — "does this make sense?"
   └──────┬─────────────────────┘
          ▼
   ┌────────────────────────────┐
   │ Intermediate Rep (Stage 4) │  flatten the tree into linear three-address code (IR)
   └──────┬─────────────────────┘
          ▼
   ┌────────────────────────────┐
   │ Code Generator (Stage 5)   │  IR → assembly / machine instructions
   └──────┬─────────────────────┘
          ▼
   ┌────────────────────────────┐
   │ Self-Host Loop (Stage 6)   │  compile SMGCC *with* SMGCC
   └────────────────────────────┘
```

### The heart: the META II metacompiler
The first two stages are powered by a small **pattern-matching engine** that reads grammar
rules and recognizes input. It blends two ideas:

- **META II** gives us the shape: named rules that both *recognize* input and *emit output*
  (e.g. build an AST node).
- **PEG** (Parsing Expression Grammars) gives us predictable matching:
  - **ordered choice** `A / B` — try A first; only if it fails, try B
  - **lookahead** `&x` / `!x` — peek without consuming (stops `if` from matching inside `iffy`)
  - **repetition** `*` `+` `?`
  - **output actions** `.OUT(...)` — attach structured output to a rule

### The self-hosting bootstrap
The grammar language is itself described in a grammar file (`meta.peg`). We feed that file
into a seed metacompiler, it generates a parser, and **that generated parser becomes the new
metacompiler**. Once this loop closes, the whole language is extended by editing one file.
This is the same trick that ultimately lets the *compiler* compile *itself*.

---

## 4. How it will be realized — the 6 stages

The project is built one rung at a time. You cannot skip a rung; each stage ships its own
`README.md` so anyone can onboard at that point.

| Stage | Name | What gets built | Status |
|---|---|---|---|
| **0** | Scaffolding | Workspace, testing framework, CI, workflow files | ✅ Complete |
| **1** | META II metacompiler | The pattern-matcher: rules, ordered choice, lookahead, repetition, output actions | ✅ Complete |
| **2** | Lexing & parsing | Use Stage 1 to parse a C subset into an **AST** | ✅ Complete |
| **3** | Semantic analysis | Symbol tables, type checking, scope validation | ✅ Complete |
| **4** | Intermediate representation | Flatten the AST into linear three-address code | ✅ Complete |
| **5** | Code generation | Translate IR into assembly | ✅ Complete |
| **6** | Self-hosting | Compile SMGCC using SMGCC | 🟡 In Progress |

---

## 5. How we work (the ground rules)

Development follows a strict, file-driven loop so that both humans and AI assistants stay
focused and don't drift:

- **Test-Driven Development (TDD)** — every feature starts with a *failing* test. The suite
  must be green on every commit, or work stops.
- **Aggressive minimality** — no code that isn't strictly needed; no speculative
  abstractions.
- **The bug loop** — on a regression, stop, write down the root cause, add a reproduction
  test, fix it, re-run everything, then continue.
- **Metacompiler paradigm** — describe syntax with grammar rules and output actions, not
  hand-rolled parsing code.

### The markdown-driven workflow
The repo's planning files are the project's externalized memory and control loop:

| File | Role |
|---|---|
| `PLAN.md` | Macro view — architecture, the 6 milestones, status |
| `RULES.md` | The immutable constitution (TDD, minimality, META II) |
| `TASK.md` | The single, scoped objective for the current session |
| `EXPL_STAGE.md` | Deep explanation of the current stage (Stage 1 today) |
| `BUGS.md` / `LOG.md` | History of regressions and root causes |

A session is: update `TASK.md` → read `RULES.md` + `PLAN.md` → produce code **and** tests →
log any regressions in `BUGS.md`.

---

## 6. Repository map

```
SGCC/
├── README.md        ← you are here
├── PLAN.md          architecture + roadmap
├── RULES.md         immutable project rules
├── TASK.md          current scoped task
├── EXPL_STAGE.md    Stage 1 deep-dive (META II metacompiler)
├── SMGCC.md         project summary
└── scripts/
    └── vault-bridge.sh   syncs these docs into the Obsidian knowledge vault
```

> **Knowledge base:** project notes are mirrored into an Obsidian "LLM-Wiki"
> (`~/obsidian-vault`) via `scripts/vault-bridge.sh`, so context is compiled once into
> linked notes instead of re-explained every session.

---

## 7. Inspirations

- **TinyCC** (Fabrice Bellard) — small, fast, comprehensible C compilation.
- **META II** (Val Schorre, 1964) — grammar rules that generate compilers.
- **VPRI STEPS** (Alan Kay) — tiny languages that define large systems.
