# COLA compiler for LW_OS (Milestone M7)

A compiler that turns **COLA** source (`.cola`) into **COLA-VM bytecode** (`.cobj`)
for the [LW_OS](/home/tiko/workspace/claude_staff/LW_OS) project. Built with the
SMGCC PEG engine; verified against LW_OS's own seed programs.

## Why this exists — the analysis

LW_OS already has the COLA **virtual machine**
(`phase8-cola-metal/cola/cola_vm.c`, 36 bytecode ops) and a tree-walking REPL.
What it does **not** have is the thing its roadmap calls **M7 — "Self-Hosting
Compiler Inside the OS"**: a compiler that emits bytecode the VM can load and run
(`compile greeter.cola` → `load greeter.cobj`). This is exactly that compiler.

## Pipeline

```
.cola source ──[reader.py]──▶ s-expr AST ──[compiler.py]──▶ COLA-VM bytecode
                                                                │
                              ┌─────────────────────────────────┤
                              ▼                                 ▼
                       [cobj.py] .cobj file            [vm.py] reference VM
                       (load into the OS)              (proves the output)
```

- **`reader.py`** — parses COLA S-expressions via `grammars/cola.peg`.
- **`compiler.py`** — lowers forms to the VM's opcodes (stack machine; every
  expression nets +1 on the stack).
- **`opcodes.py`** — opcode numbers, kept identical to `cola_vm.h`.
- **`vm.py`** — a faithful Python mirror of `cola_vm.c`, so compiled output can be
  validated without QEMU.
- **`cobj.py`** — `.cobj` serialize/deserialize + a disassembler.

## Use it

```bash
python3 colac.py examples/cola/factorial.cola            # -> factorial.cobj
python3 colac.py examples/cola/factorial.cola --run      # prints 3628800
python3 colac.py examples/cola/fib.cola --run            # 011235813213455
python3 colac.py examples/cola/factorial.cola --dis      # disassembly
python3 -m unittest tests.test_cola                      # 20 tests
```

## Verified against the real OS

The four seed programs baked into the LW_OS image
(`phase8-cola-metal/fs/seed.h`) compile and produce **byte-for-byte the same
output** the on-OS VM prints:

| program | output |
|---|---|
| `hello.cola` | `Hello from COLA on bare metal!` |
| `factorial.cola` | `3628800` (10!) |
| `fib.cola` | `011235813213455` (fib 0..10) |
| `counter.cola` | defines `inc`/`dec`/`show`; drives to `3` |

## Language supported

Literals (int, string, `true`/`false`/`nil`); `def`/`set`; `if`; `while`; `do`;
`fn`/`call`; `send`; arithmetic `+ - * / %`; comparison `= < > <= >=`; `not`;
`concat`; `print`/`nl`. (`<=`/`>=` desugar to `not (> )` / `not (< )` because the
VM only has `LT`/`GT`/`EQ`.)

## Known limitation (inherited from the VM)

The VM's `OP_MAKE_CLOSURE` does **not** capture variables, so a closure's free
variables resolve to **globals**, not enclosing-function locals. Top-level
recursion (`fact`, `fib`) and global mutation (`counter`) work; a closure that
captures an *outer function's parameter* would not (that path only works in the
tree-walking REPL). This matches the bytecode VM's actual behavior.

## Integrating into LW_OS (M7)

LW_OS is untouched (analyzed read-only). `cobj_load.c` here is a **reference
loader**: it parses a `.cobj` into a `ColaProgram` (via `cola_prog_emit` /
`cola_prog_add_const`) and runs it with `cola_vm_run`. To wire M7 in-OS you would
either (a) port `compiler.py` to COLA/C so the OS compiles natively, or (b) ship
`.cobj` files and add `cobj_load.c` so the OS executes pre-compiled modules. The
`.cobj` text format is line-oriented precisely so it's trivial to parse with
`klibc` inside the kernel.
