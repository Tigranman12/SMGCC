# Graph Report - .  (2026-06-27)

## Corpus Check
- Corpus is ~27,399 words - fits in a single context window. You may not need a graph.

## Summary
- 697 nodes · 1639 edges · 33 communities (18 shown, 15 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 275 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_COLA ReaderParser|COLA Reader/Parser]]
- [[_COMMUNITY_COLA Object Format|COLA Object Format]]
- [[_COMMUNITY_Integration Tests|Integration Tests]]
- [[_COMMUNITY_COLA Grammar|COLA Grammar]]
- [[_COMMUNITY_IR Builder|IR Builder]]
- [[_COMMUNITY_Stage 6 Tests|Stage 6 Tests]]
- [[_COMMUNITY_PEG Engine Core|PEG Engine Core]]
- [[_COMMUNITY_Documentation & Concepts|Documentation & Concepts]]
- [[_COMMUNITY_Calculator Demo|Calculator Demo]]
- [[_COMMUNITY_Semantic Analyzer|Semantic Analyzer]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 31|Community 31]]

## God Nodes (most connected - your core abstractions)
1. `RunTests` - 57 edges
2. `ColaVM` - 49 edges
3. `Lit` - 39 edges
4. `ParseError` - 33 edges
5. `_Reader` - 30 edges
6. `load()` - 30 edges
7. `_try()` - 29 edges
8. `SemanticError` - 25 edges
9. `Range` - 25 edges
10. `CalcTests` - 25 edges

## Surprising Connections (you probably didn't know these)
- `META II Metacompiler` --semantically_similar_to--> `VPRI STEPS`  [INFERRED] [semantically similar]
  EXPL_STAGE.md → README.md
- `CobjTests` --uses--> `ColaVM`  [INFERRED]
  tests/test_cola.py → cola/vm.py
- `EvalTests` --uses--> `ColaVM`  [INFERRED]
  tests/test_cola.py → cola/vm.py
- `ReaderTests` --uses--> `ColaVM`  [INFERRED]
  tests/test_cola.py → cola/vm.py
- `SeedProgramTests` --uses--> `ColaVM`  [INFERRED]
  tests/test_cola.py → cola/vm.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **META II + PEG Parsing Paradigm** — meta_ii, peg_grammar, peg_engine [EXTRACTED 0.95]
- **COLA Compiler Pipeline** — cola_language, cola_vm, cobj_format, lw_os_project [EXTRACTED 0.90]
- **SMGCC Compiler Pipeline Stages** — stage_1, stage_2, stage_3, stage_4, stage_5 [EXTRACTED 0.95]

## Communities (33 total, 15 thin omitted)

### Community 0 - "COLA Reader/Parser"
Cohesion: 0.06
Nodes (55): _grammar(), COLA reader — source text to an s-expression AST, via the SMGCC PEG engine.  AST, load(), Grammar, Seed grammar loader — reads a `.peg` grammar file into engine nodes.  This hand-, Parse grammar `text` into a Grammar. The first rule is the start rule., Act, And (+47 more)

### Community 1 - "COLA Object Format"
Cohesion: 0.07
Nodes (25): disassemble(), dumps(), loads(), `.cobj` object-file format: serialize/deserialize a compiled Program, plus a hum, ColaCompileError, compile_forms(), Compiler, Program (+17 more)

### Community 4 - "IR Builder"
Cohesion: 0.09
Nodes (9): ir_to_string(), IRBuilder, Intermediate Representation — Stage 4.  Flattens the AST into linear three-addre, Generate IR for an expression. Returns the temp holding the result., Pretty-print IR instructions for debugging., Builds IR instructions from an AST., Build IR from a program AST. Returns list of instructions., IRTests (+1 more)

### Community 5 - "Stage 6 Tests"
Cohesion: 0.08
Nodes (17): _asm_contains(), _exit_code(), KitchenSinkTest, LoopEdgeCasesTest, PointerEdgeCasesTest, Stage 6 tests: comprehensive integration + self-hosting readiness.  Exercises AL, Deeply nested structs, struct arrays of structs, pointer chains., Pointer arithmetic, reassignment, null-ish patterns. (+9 more)

### Community 6 - "PEG Engine Core"
Cohesion: 0.18
Nodes (36): Input, MatchResult, ParseState, Grammar, fail_result(), grammar_add_rule(), grammar_init(), input_at() (+28 more)

### Community 7 - "Documentation & Concepts"
Cohesion: 0.11
Nodes (37): Abstract Syntax Tree, Backtracking Mechanism, Bug Loop Process, Bug Log, Function Specification, Stage 1 Explanation, Seed Grammar Loader, Left Recursion Problem (+29 more)

### Community 8 - "Calculator Demo"
Cohesion: 0.11
Nodes (13): evaluate(), grammar_text(), load_calc(), Arithmetic playground built on the META II/PEG engine.  The grammar lives in ../, Load the arithmetic grammar from disk into a runnable Grammar., Walk the AST and compute its value (C-style integer arithmetic)., Render the AST as a readable S-expression., show_ast() (+5 more)

### Community 9 - "Semantic Analyzer"
Cohesion: 0.12
Nodes (13): Exception, analyze(), _Analyzer, Semantic analyzer — Stage 3.  Walks the AST produced by the parser and verifies:, Evaluate a constant expression (for enum values)., Raised when the analyzer finds a semantic error., A single scope level mapping names to types., Stack of scopes for nested block handling. (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.19
Nodes (10): CompileError, Gen, Walk the AST to populate var_types for struct variables., Compute byte offset of a member within a struct., Generate code to load address of struct member into %rax., Resolve the type of an expression (for struct member access)., Resolve the struct name of an expression., Get the type of a member within a struct. (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.13
Nodes (16): _collect_locals(), generate(), x86-64 code generator — Stages 3-5 folded into one pass.  Strategy: a classic st, All names that need a stack slot: params first, then every declared var.     Ret, AST -> x86-64 assembly text., compile_to_asm(), compile_to_exe(), main() (+8 more)

### Community 14 - "Community 14"
Cohesion: 0.33
Nodes (3): _Reader, Reference to another named rule., Ref

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (3): load_c(), Load the C-subset grammar from disk into a runnable Grammar., ParseTests

### Community 16 - "Community 16"
Cohesion: 0.36
Nodes (6): COLA Bytecode Format, COLA Language, COLA-VM opcode numbers — MUST match the enum order in LW_OS/phase8-cola-metal/co, COLA Compiler README, Reference COLA VM in Python — a faithful mirror of LW_OS/phase8-cola-metal/cola/, LW_OS Operating System

### Community 17 - "Community 17"
Cohesion: 0.46
Nodes (7): Cola, cobj_load(), cobj_load_run(), next_line(), op_from_name(), parse_int(), ColaProgram

### Community 22 - "Community 22"
Cohesion: 0.83
Nodes (3): fact(), fib(), main()

## Knowledge Gaps
- **10 isolated node(s):** `ColaProgram`, `smgcc`, `Input`, `Bug Log`, `CI Workflow` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ColaCompileError` connect `COLA Object Format` to `Semantic Analyzer`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Why does `ParseError` connect `COLA Reader/Parser` to `Integration Tests`, `Stage 6 Tests`, `Calculator Demo`, `Semantic Analyzer`, `Community 12`, `Community 15`?**
  _High betweenness centrality (0.149) - this node is a cross-community bridge._
- **Why does `RunTests` connect `Integration Tests` to `COLA Reader/Parser`, `Semantic Analyzer`, `Community 11`, `Community 12`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `RunTests` (e.g. with `SemanticError` and `CompileError`) actually correct?**
  _`RunTests` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `ColaVM` (e.g. with `CobjTests` and `EvalTests`) actually correct?**
  _`ColaVM` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Lit` (e.g. with `Grammar` and `_Reader`) actually correct?**
  _`Lit` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `ParseError` (e.g. with `ParseTests` and `RunTests`) actually correct?**
  _`ParseError` has 23 INFERRED edges - model-reasoned connections that need verification._