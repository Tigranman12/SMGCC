# Current Task: Stage 6 — Self-Hosting

This document defines the highly-scoped objective for the current coding session.

## Objective
Compile SMGCC using SMGCC to achieve complete independence. The compiler should be able to parse, analyze, and generate code for its own source code.

## Completed This Session
- [x] Fixed nested struct member access bugs (`_resolve_struct_name`, `_resolve_type`)
- [x] Fixed `&` operator for subscript lvalues (`&arr[0]`)
- [x] Added string literal support (grammar, analyzer, codegen)
- [x] Added `.` (any character) support to grammar loader
- [x] Added escape sequence processing to grammar loader literals
- [x] Written 26 comprehensive integration tests (Stage 6)
- [x] Started C PEG engine (works with gcc, needs SMGCC-compatible subset)

## Remaining Checklist
- [ ] Rewrite PEG engine in SMGCC-compatible C subset (no `#include`, `static`, `typedef`)
- [ ] Rewrite grammar loader in C
- [ ] Rewrite C grammar actions in C
- [ ] Rewrite semantic analyzer in C
- [ ] Rewrite code generator in C
- [ ] Bootstrap: compile SMGCC-C with SMGCC-Python
- [ ] Self-test: compile SMGCC-C with itself
- [ ] Document the self-hosting achievement

## Notes
Self-hosting requires rewriting the compiler in the C subset SMGCC already supports. The C version must avoid:
- Preprocessor directives (`#include`, `#define`)
- `static`, `typedef`, `const`
- String literals in source (use integer arrays or compute at runtime)
- Multiple source files

The path forward: write a single-file C version using only supported features, compile it with the Python SMGCC, then use the resulting binary to compile itself.
