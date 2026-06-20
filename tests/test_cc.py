"""Stage 2-5 tests: parse C, generate asm, link, run, check exit codes.

Run: python3 -m unittest discover -s tests
The integration tests need `as` and `ld` (binutils) on PATH.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from smgcc.cgrammar import load_c
from smgcc.driver import compile_to_asm, compile_to_exe
from smgcc.cgen import CompileError
from smgcc.peg import ParseError

_HAVE_TOOLS = shutil.which("as") and shutil.which("ld")


class ParseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_c()

    def test_minimal_function(self):
        ast = self.g.parse("int main() { return 0; }")
        self.assertEqual(ast, ("program", [("func", "main", [], ("block", [("ret", ("num", 0))]))]))

    def test_precedence_in_ast(self):
        ast = self.g.parse("int main() { return 2 + 3 * 4; }")
        ret = ast[1][0][3][1][0]
        self.assertEqual(ret, ("ret", ("bin", "+", ("num", 2), ("bin", "*", ("num", 3), ("num", 4)))))

    def test_params_and_call(self):
        self.g.parse("int add(int a, int b) { return a + b; } int main() { return add(2, 3); }")

    def test_undeclared_variable_is_error(self):
        with self.assertRaises(CompileError):
            compile_to_asm("int main() { return x; }")

    def test_syntax_error(self):
        with self.assertRaises(ParseError):
            self.g.parse("int main() { return 1 }")  # missing ';'


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class RunTests(unittest.TestCase):
    def _exit_code(self, src: str) -> int:
        d = tempfile.mkdtemp(prefix="smgcc_test_")
        exe = os.path.join(d, "prog")
        compile_to_exe(src, exe)
        return subprocess.run([exe]).returncode

    def test_return_constant(self):
        self.assertEqual(self._exit_code("int main() { return 42; }"), 42)

    def test_arithmetic(self):
        self.assertEqual(self._exit_code("int main() { return 2 + 3 * 4 - 1; }"), 13)

    def test_division_and_modulo(self):
        self.assertEqual(self._exit_code("int main() { return 20 / 3 + 20 % 3; }"), 8)

    def test_locals(self):
        self.assertEqual(self._exit_code("int main() { int x = 5; int y = 6; return x * y; }"), 30)

    def test_if_else(self):
        self.assertEqual(self._exit_code("int main() { int x = 3; if (x > 2) return 10; else return 20; }"), 10)

    def test_while_loop_factorial(self):
        src = "int main() { int n = 5; int r = 1; while (n > 0) { r = r * n; n = n - 1; } return r; }"
        self.assertEqual(self._exit_code(src), 120)

    def test_recursion(self):
        src = ("int fact(int n) { if (n < 2) return 1; return n * fact(n - 1); }"
               "int main() { return fact(5); }")
        self.assertEqual(self._exit_code(src), 120)

    def test_comparison_result(self):
        self.assertEqual(self._exit_code("int main() { return 7 == 7; }"), 1)
        self.assertEqual(self._exit_code("int main() { return 7 != 7; }"), 0)


if __name__ == "__main__":
    unittest.main()
