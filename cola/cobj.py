"""`.cobj` object-file format: serialize/deserialize a compiled Program, plus a
human-readable disassembler.

Text format (line-oriented, trivial to parse with klibc inside the OS):

    COBJ1
    consts <N>
    int <idx> <value>
    str <idx> <text-to-end-of-line>
    sym <idx> <name>
    code <M>
    <idx> <OPNAME> <arg>
    ...
"""
from .compiler import Program
from .opcodes import OPCODES, NAMES


def dumps(prog: Program) -> str:
    lines = ["COBJ1", f"consts {len(prog.consts)}"]
    for i, (kind, value) in enumerate(prog.consts):
        if kind == "str":
            lines.append(f"str {i} {value}")
        else:
            lines.append(f"{kind} {i} {value}")
    lines.append(f"code {len(prog.code)}")
    for i, (op, arg) in enumerate(prog.code):
        lines.append(f"{i} {op} {arg}")
    return "\n".join(lines) + "\n"


def loads(text: str) -> Program:
    prog = Program()
    lines = text.splitlines()
    assert lines[0] == "COBJ1", "not a COBJ1 file"
    i = 1
    n_consts = int(lines[i].split()[1]); i += 1
    for _ in range(n_consts):
        parts = lines[i].split(" ", 2)
        kind = parts[0]
        if kind == "int":
            prog.consts.append(("int", int(parts[2])))
        elif kind == "sym":
            prog.consts.append(("sym", parts[2]))
        elif kind == "str":
            prog.consts.append(("str", parts[2]))
        i += 1
    n_code = int(lines[i].split()[1]); i += 1
    for _ in range(n_code):
        parts = lines[i].split()
        prog.code.append([parts[1], int(parts[2])])
        i += 1
    return prog


def disassemble(prog: Program) -> str:
    out = ["; constants"]
    for i, (kind, value) in enumerate(prog.consts):
        out.append(f";  [{i}] {kind} {value!r}")
    out.append("; code")
    # ops whose arg names a constant -> annotate
    const_arg = {"PUSH_CONST", "PUSH_SYM", "PUSH_GLOBAL", "STORE_GLOBAL"}
    jump_arg = {"JUMP", "BRANCH_FALSE", "BRANCH_TRUE", "MAKE_CLOSURE"}
    for i, (op, arg) in enumerate(prog.code):
        note = ""
        if op in const_arg and arg < len(prog.consts):
            note = f"   ; {prog.consts[arg][1]!r}"
        elif op in jump_arg:
            note = f"   ; -> {arg}"
        out.append(f"{i:4} {op:<14} {arg}{note}")
    return "\n".join(out) + "\n"
