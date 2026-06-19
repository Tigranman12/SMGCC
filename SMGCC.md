# Project Summary: Minimalist Self-Hosting C Compiler

## Core Objective
Build a custom C compiler from scratch that is exceptionally small, highly efficient, and logically sound. The project combines raw compilation speed with extreme code-reduction techniques.

## Key Architectural Inspirations
*   **TinyCC (Fabrice Bellard):** Pragmatic, fast, and minimalistic code generation.
*   **META II (Val Schorre) & VPRI STEPS (Alan Kay):** Utilizing a metacompiler/pattern-matching engine (Domain-Specific Languages) to define syntax rules rather than writing massive, hand-coded recursive descent parsers. META II is the direct Stage 1 model: grammar-driven recognition plus explicit output actions.

## Development & Engineering Philosophy
*   **Strict Test-Driven Development (TDD):** Every feature must begin with a failing test.
*   **The Iterative "Bug Loop":** If a regression or logical loop occurs, development stops. A new test is written specifically for the edge case, the bug is fixed, and all previous stages are re-tested to guarantee system stability.
*   **Junior-Friendly Documentation:** Every project stage must include a `README.md` that clearly explains the inputs, outputs, and logic for easy onboarding.

---

# AI Collaboration Strategy: Markdown-Driven Workflow

To maintain absolute focus and prevent the AI from hallucinating or losing context, the project relies on a strict, file-based prompting system. 

## The Core Context Files
*   `PLAN.md`: The macro view containing the architectural roadmap, the 6 core milestones, and the overall completion status.
*   `RULES.md`: The immutable project constitution (e.g., TDD only, keep code tiny, strictly use the metacompiler paradigm).
*   `TASK.md`: The micro-view containing the immediate, highly-scoped objective for the current AI coding session.
*   `BUGS.md` / `LOG.md`: The historical log of regressions, edge cases, and root causes to prevent the AI from repeating past errors.

## The Execution Loop
1. Update `TASK.md` with the specific next step.
2. Prompt the AI: *"Read `TASK.md` for the current objective. Review `RULES.md` for constraints. Check `PLAN.md` for architecture. Output code and tests."*
3. Implement, run tests, and immediately document regressions in `BUGS.md` if the code fails.

---

# Project Milestones

*   **Stage 0:** Scaffolding, Git setup, and CI/testing framework initialization.
*   **Stage 1 (META II Metacompiler):** Build a tiny META II-style pattern-matching engine with PEG-like ordered choice to read syntax rules and emit structured parser/AST output.
*   **Stage 2 (Lexing/Parsing):** Use the metacompiler to parse a subset of C into an Abstract Syntax Tree (AST).
*   **Stage 3 (Semantic Analysis):** Implement symbol tables to verify types and variable declarations.
*   **Stage 4 (Intermediate Representation):** Flatten the AST into linear Three-Address Code (IR).
*   **Stage 5 (Code Generation):** Translate IR into target Assembly language.
*   **Stage 6 (Self-Hosting):** Use the compiler to successfully compile its own source code.
