# Project Plan: Minimalist Self-Hosting C Compiler (SMGCC)

This document maps out our high-level architecture, the 6 core milestones, and the overall completion status of the SMGCC project.

The parsing architecture is explicitly based on **META II**: a small
metacompiler reads grammar rules, matches input patterns, and can attach
semantic output actions to those rules. We will use modern PEG-style ordered
choice and backtracking, but the core logic stays META II: grammar-driven
recognition first, generated parser/compiler behavior second.

## Project Macro View & Roadmap

```
+------------------------------------------------------------+
|                       SMGCC Pipeline                       |
+------------------------------------------------------------+
|                                                            |
|  [ C Source ] --> [ META II-style Parser (Stage 1/2) ]      |
|                             |                              |
|                             v                              |
|                    [ Syntax Tree (AST) ]                   |
|                             |                              |
|                             v                              |
|                  [ Semantic Analyzer (Stage 3) ]           |
|                             |                              |
|                             v                              |
|                 [ Intermediate Rep (Stage 4) ]             |
|                             |                              |
|                             v                              |
|                  [ Codegen / ASM (Stage 5) ]               |
|                             |                              |
|                             v                              |
|                 [ Self-Host Loop (Stage 6) ]               |
|                                                            |
+------------------------------------------------------------+
```

Our journey is structured into 6 sequential stages designed to take us from blank canvas to a self-hosting compiler.

---

## Completion Status & Milestones

| Stage | Name | Description | Status |
|---|---|---|---|
| **Stage 0** | **Scaffolding** | Setup environment, core testing frameworks, workflow files. | 🟡 In Progress |
| **Stage 1** | **META II Metacompiler** | Build a tiny META II-style pattern matcher that reads grammar rules and supports output actions. | ⚪ Not Started |
| **Stage 2** | **Lexing & Parsing** | Use the Stage 1 META II metacompiler to parse a subset of C into an AST. | ⚪ Not Started |
| **Stage 3** | **Semantic Analysis**| Type-checking, scope validation, and symbol table generation. | ⚪ Not Started |
| **Stage 4** | **Intermediate Rep** | Flatten AST into stable, linear Three-Address Code (IR). | ⚪ Not Started |
| **Stage 5** | **Code Generation**  | Translate IR into low-level machine instructions / Assembly. | ⚪ Not Started |
| **Stage 6** | **Self-Hosting**    | Compile SMGCC using SMGCC to achieve complete independence. | ⚪ Not Started |

---

## Next Milestones & Objectives

### Stage 0: Scaffolding (Immediate Target)
- Setup workspace configuration.
- Initialize testing framework and CI structure.
- Define initial workflow boundaries (`RULES.md`, `TASK.md`, `PLAN.md`).

### Stage 1: META II Metacompiler (Upcoming Target)
- Design and implement a tiny META II-style recognizer with PEG-like ordered choice.
- Support grammar rules, sequence, ordered alternatives, repetition, literals, rule references, and semantic output actions.
- Target a simple grammar definition language that can describe its own parser.
- Establish the bootstrap process: seed recognizer -> meta grammar -> generated parser.
