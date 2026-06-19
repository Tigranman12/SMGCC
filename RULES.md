# Project Constitution: SMGCC Immutable Rules

This document establishes the foundational design, engineering, and architectural constraints that are strictly immutable. All contributors—human and AI alike—must adhere to these rules without exception.

---

## 1. Test-Driven Development (TDD) Rule
- **First, the Test:** Every new feature, logic path, or bug fix must start with a failing test case.
- **Strict Isolation:** Code changes must not be written without a corresponding test validating the behavior.
- **No Regressions:** The test suite must run clean on every commit. If any existing tests fail, implementation halts immediately.

## 2. Code Minimality Rule
- **Aggressive Simplicity:** Do not write a line of code that is not strictly necessary. 
- **Avoid Over-Engineering:** No "just in case" features, extra abstractions, or future-proofing. Solve the problem in front of you as simply and elegantly as possible.
- **Tiny Source:** Keep file lengths short, code blocks highly cohesive, and dependencies close to zero.

## 3. The Metacompiler Paradigm
- **Parser Generation:** We do not write large, manual, recursive descent parsers. We describe the language rules using a Parsing Expression Grammar (PEG) domain-specific language (DSL).
- **Self-Generating:** Our parser must be parsed by a parser that our metacompiler generates. This bootstrap loop is vital for self-hosting.
- **Pattern Matching:** Use declarative pattern matching rather than convoluted procedural parsing states wherever possible.

## 4. Stability & Historical Logging
- **The Bug Loop Rule:** If a regression or logical loop occurs, development stops. 
- **Documentation First:** Document the regression in `BUGS.md`/`LOG.md` along with its root cause.
- **Reproduction Case:** Write a reproduction test, fix the issue, run the complete suite, and only then proceed.

## 5. Architectural Quality Standards
- **Explicit Types:** Use explicit typing, static analysis, and proper error handling. Hacks, bypasses, or suppressing type errors (such as `any` or forced type casts) are strictly forbidden.
- **Documentation on Onboarding:** Each stage must include clear inputs, outputs, and explanations in a `README.md` to ensure any junior developer can jump into the codebase immediately.
- **Strict Composition:** Prefer clean function composition and interface delegation over complex class hierarchies.
