"""COLA compiler tests: parse -> compile -> run on the reference VM, and check
the output matches what the real LW_OS COLA VM would print.

Run: python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from cola.reader import read
from cola.compiler import compile_forms, ColaCompileError
from cola.vm import ColaVM
from cola.cobj import dumps, loads, disassemble

_EXAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "examples", "cola")


def run(src: str) -> str:
    return ColaVM(compile_forms(read(src))).run()


def run_file(name: str) -> str:
    with open(os.path.join(_EXAMPLES, name), encoding="utf-8") as f:
        return run(f.read())


class ReaderTests(unittest.TestCase):
    def test_atoms_and_list(self):
        self.assertEqual(read("(+ 1 2)"), [("list", [("sym", "+"), ("int", 1), ("int", 2)])])

    def test_string(self):
        self.assertEqual(read('(print "hi there")'),
                         [("list", [("sym", "print"), ("str", "hi there")])])

    def test_nested(self):
        forms = read("(if (< n 1) n (call f n))")
        self.assertEqual(forms[0][0], "list")


class EvalTests(unittest.TestCase):
    def test_arithmetic_precedence(self):
        self.assertEqual(run("(print (+ 2 (* 3 4)))"), "14")

    def test_fold(self):
        self.assertEqual(run("(print (+ 1 2 3 4))"), "10")

    def test_comparison_and_not(self):
        self.assertEqual(run("(print (<= 3 3))"), "true")
        self.assertEqual(run("(print (>= 2 5))"), "false")

    def test_def_and_use(self):
        self.assertEqual(run("(def x 21) (print (+ x x))"), "42")

    def test_if_else(self):
        self.assertEqual(run("(print (if (> 3 2) 100 200))"), "100")

    def test_while_accumulate(self):
        src = "(def s 0) (def i 1) (while (<= i 5) (do (set s (+ s i)) (set i (+ i 1)))) (print s)"
        self.assertEqual(run(src), "15")

    def test_lambda_call(self):
        self.assertEqual(run("(def sq (fn (x) (* x x))) (print (call sq 9))"), "81")

    def test_string_print(self):
        self.assertEqual(run('(print "hello")'), "hello")

    def test_concat(self):
        self.assertEqual(run('(print (concat "ab" "cd"))'), "abcd")

    def test_send_to_integer(self):
        self.assertEqual(run("(print (send 3 + 4))"), "7")


class SeedProgramTests(unittest.TestCase):
    """The four LW_OS seed programs must produce exactly the OS's output."""

    def test_hello(self):
        self.assertEqual(run_file("hello.cola"), "Hello from COLA on bare metal!")

    def test_factorial(self):
        self.assertEqual(run_file("factorial.cola"), "3628800")   # 10!

    def test_fib(self):
        # fib(0..10) printed with no separators
        self.assertEqual(run_file("fib.cola"), "011235813213455")

    def test_counter_via_repl(self):
        # load counter, then drive it like the REPL would
        with open(os.path.join(_EXAMPLES, "counter.cola"), encoding="utf-8") as f:
            src = f.read()
        src += "(call inc) (call inc) (call inc) (print (call show))"
        # inc returns count; show prints count and returns it; final print repeats it
        self.assertEqual(run(src), "33")


class CobjTests(unittest.TestCase):
    def test_roundtrip(self):
        prog = compile_forms(read("(def x 5) (print (* x x))"))
        text = dumps(prog)
        back = loads(text)
        self.assertEqual(back.code, prog.code)
        self.assertEqual(back.consts, prog.consts)
        self.assertEqual(ColaVM(back).run(), "25")

    def test_disassemble_runs(self):
        prog = compile_forms(read("(print 1)"))
        self.assertIn("PUSH_INT", disassemble(prog))

    def test_undeclared_form_errors(self):
        with self.assertRaises(ColaCompileError):
            compile_forms(read("(def)"))


if __name__ == "__main__":
    unittest.main()
