"""COLA compiler driver / CLI. See ../colac.py.

    python3 colac.py prog.cola              # -> prog.cobj
    python3 colac.py prog.cola -o out.cobj
    python3 colac.py prog.cola --run        # compile + run on the reference VM
    python3 colac.py prog.cola --dis        # disassemble
"""
import os
import sys

from .reader import read
from .compiler import compile_forms, ColaCompileError
from .cobj import dumps, disassemble
from .vm import ColaVM


def compile_text(src: str):
    return compile_forms(read(src))


def main(argv) -> int:
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    src_file = None
    out_path = None
    run = dis = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-o":
            i += 1
            out_path = args[i]
        elif a == "--run":
            run = True
        elif a == "--dis":
            dis = True
        elif a.startswith("-"):
            print(f"unknown option: {a}", file=sys.stderr)
            return 2
        else:
            src_file = a
        i += 1

    if src_file is None:
        print("error: no input file", file=sys.stderr)
        return 2

    with open(src_file, encoding="utf-8") as f:
        src = f.read()

    try:
        prog = compile_text(src)
    except ColaCompileError as e:
        print(f"{src_file}: compile error: {e}", file=sys.stderr)
        return 1

    if dis:
        print(disassemble(prog), end="")
        return 0
    if run:
        print(ColaVM(prog).run(), end="")
        return 0

    if out_path is None:
        base = os.path.splitext(src_file)[0]
        out_path = base + ".cobj"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dumps(prog))
    print(f"wrote {out_path}  ({len(prog.code)} instrs, {len(prog.consts)} consts)")
    return 0
