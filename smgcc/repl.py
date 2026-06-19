"""Interactive playground for the SMGCC Stage 1 engine.

    python3 run.py                 # interactive REPL
    python3 run.py "1 + 2 * 3"     # one-shot
"""
from .calc import load_calc, evaluate, show_ast, grammar_text
from .peg import ParseError

BANNER = """\
SMGCC Stage 1 — META II / PEG playground
Type an arithmetic expression (e.g.  (1 + 2) * 3 - 4).
Commands:  :grammar   show the .peg grammar
           :help      this help
           :q         quit
"""

HELP = """\
Enter expressions with + - * / and parentheses, integers only.
For each line you'll see the parsed AST and the evaluated result.
The grammar is loaded from grammars/arith.peg — edit it and re-run.
"""


def _eval_line(g, line: str) -> int:
    """Parse + evaluate one line, printing AST and result. Returns 0/1 status."""
    try:
        ast = g.parse(line)
    except ParseError as e:
        print(e)
        return 1
    print(f"  ast: {show_ast(ast)}")
    print(f"  =    {evaluate(ast)}")
    return 0


def run(argv):
    g = load_calc()

    # one-shot mode
    if len(argv) > 1:
        return _eval_line(g, " ".join(argv[1:]))

    # interactive mode
    print(BANNER)
    while True:
        try:
            line = input("smgcc> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in (":q", ":quit", "exit", "quit"):
            break
        if line == ":help":
            print(HELP)
            continue
        if line == ":grammar":
            print(grammar_text())
            continue
        _eval_line(g, line)
    return 0
