"""Compiler driver — source text to a native executable.

Pipeline:  C source -> [cgrammar] AST -> [analyze] check -> [cgen] x86-64 asm -> as -> ld -> ELF.

Usage (via ../cc.py):
    python3 cc.py program.c                 # -> a.out
    python3 cc.py program.c -o program
    python3 cc.py program.c --emit-asm      # print assembly, don't link
    python3 cc.py program.c --run           # build to a temp file and run it
"""
import os
import subprocess
import sys
import tempfile

from .cgrammar import load_c
from .cgen import generate, CompileError
from .peg import ParseError
from .analyze import analyze, SemanticError


def _strip_comments(src: str) -> str:
    """Remove // and /* */ comments. Safe: the C subset has no string/char literals."""
    out = []
    i, n = 0, len(src)
    while i < n:
        if src[i] == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
        elif src[i] == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def compile_to_asm(src: str) -> str:
    """C source -> assembly text. Raises ParseError, SemanticError, or CompileError."""
    ast = load_c().parse(_strip_comments(src))
    table = analyze(ast)
    return generate(ast, table.get("enum_values", {}), table.get("structs", {}))


def compile_to_exe(src: str, out_path: str, keep_asm: str = None) -> str:
    """C source -> linked executable at out_path. Returns out_path."""
    asm = compile_to_asm(src)
    tmp = tempfile.mkdtemp(prefix="smgcc_")
    s_path = keep_asm or os.path.join(tmp, "a.s")
    o_path = os.path.join(tmp, "a.o")
    with open(s_path, "w", encoding="utf-8") as f:
        f.write(asm)
    subprocess.run(["as", "-o", o_path, s_path], check=True)
    subprocess.run(["ld", "-o", out_path, o_path], check=True)
    return out_path


def main(argv) -> int:
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    src_file = None
    out_path = "a.out"
    emit_asm = False
    run = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-o":
            i += 1
            out_path = args[i]
        elif a == "--emit-asm":
            emit_asm = True
        elif a == "--run":
            run = True
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
        if emit_asm:
            print(compile_to_asm(src), end="")
            return 0
        if run:
            exe = compile_to_exe(src, os.path.join(tempfile.mkdtemp(), "prog"))
            return subprocess.run([exe]).returncode
        compile_to_exe(src, out_path)
        print(f"wrote {out_path}")
        return 0
    except ParseError as e:
        print(f"{src_file}: syntax error\n{e}", file=sys.stderr)
        return 1
    except SemanticError as e:
        print(f"{src_file}: semantic error: {e}", file=sys.stderr)
        return 1
    except CompileError as e:
        print(f"{src_file}: compile error: {e}", file=sys.stderr)
        return 1
