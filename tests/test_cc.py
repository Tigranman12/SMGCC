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
from smgcc.analyze import SemanticError
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
        with self.assertRaises(SemanticError):
            compile_to_asm("int main() { return x; }")

    def test_syntax_error(self):
        with self.assertRaises(ParseError):
            self.g.parse("int main() { return 1 }")  # missing ';'


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class RunTests(unittest.TestCase):
    """Integration tests: compile C, run, check exit code.
    Exit codes are mod 256 (Linux syscall limit)."""

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

    def test_for_loop_sum(self):
        src = "int main() { int s = 0; int i; for (i = 1; i <= 10; i = i + 1) s = s + i; return s; }"
        self.assertEqual(self._exit_code(src), 55)

    def test_for_loop_with_decl(self):
        src = "int main() { int s = 0; for (int i = 0; i < 5; i = i + 1) s = s + i; return s; }"
        self.assertEqual(self._exit_code(src), 10)

    def test_break(self):
        src = "int main() { int i; for (i = 0; i < 100; i = i + 1) { if (i == 7) break; } return i; }"
        self.assertEqual(self._exit_code(src), 7)

    def test_continue(self):
        # sum only even numbers 0..9 using continue
        src = ("int main() { int s = 0; int i; for (i = 0; i < 10; i = i + 1) {"
               " if (i % 2 == 1) continue; s = s + i; } return s; }")
        self.assertEqual(self._exit_code(src), 20)

    def test_logical_and(self):
        self.assertEqual(self._exit_code("int main() { return 3 > 2 && 5 > 4; }"), 1)
        self.assertEqual(self._exit_code("int main() { return 3 > 2 && 1 > 4; }"), 0)

    def test_logical_or(self):
        self.assertEqual(self._exit_code("int main() { return 1 > 9 || 2 > 1; }"), 1)

    def test_short_circuit_does_not_divide_by_zero(self):
        # if && did not short-circuit, the 1/0 would trap; instead it returns 0
        src = "int main() { int x = 0; if (x != 0 && 1 / x > 0) return 1; return 0; }"
        self.assertEqual(self._exit_code(src), 0)

    def test_comments(self):
        src = ("int main() { // line comment\n"
               "  int x = 21; /* block\n comment */ return x + x; }")
        self.assertEqual(self._exit_code(src), 42)

    def test_nested_loops(self):
        src = ("int main() { int c = 0; int i; int j;"
               " for (i = 0; i < 3; i = i + 1)"
               "   for (j = 0; j < 3; j = j + 1) c = c + 1;"
               " return c; }")
        self.assertEqual(self._exit_code(src), 9)

    def test_do_while(self):
        src = "int main() { int i = 0; int s = 0; do { s = s + i; i = i + 1; } while (i < 5); return s; }"
        self.assertEqual(self._exit_code(src), 10)

    def test_do_while_once(self):
        src = "int main() { int x = 0; do { x = 1; } while (0); return x; }"
        self.assertEqual(self._exit_code(src), 1)

    def test_do_while_with_break(self):
        src = ("int main() { int i = 0; int s = 0;"
               " do { if (i == 3) break; s = s + i; i = i + 1; } while (i < 10);"
               " return s; }")
        self.assertEqual(self._exit_code(src), 3)

    def test_do_while_with_continue(self):
        src = ("int main() { int i = 0; int s = 0;"
               " do { i = i + 1; if (i % 2 == 0) continue; s = s + i; } while (i < 5);"
               " return s; }")
        self.assertEqual(self._exit_code(src), 9)

    def test_enum_basic(self):
        src = "enum { RED, GREEN, BLUE }; int main() { return GREEN; }"
        self.assertEqual(self._exit_code(src), 1)

    def test_enum_explicit_values(self):
        src = "enum { X = 10, Y = 20, Z }; int main() { return Z; }"
        self.assertEqual(self._exit_code(src), 21)

    def test_enum_in_switch(self):
        src = ("enum { RED, GREEN, BLUE };"
               " int main() { int x = BLUE;"
               " switch (x) { case RED: return 1; case GREEN: return 2; case BLUE: return 3; }"
               " return 0; }")
        self.assertEqual(self._exit_code(src), 3)

    def test_struct_member_access(self):
        src = ("struct Point { int x; int y; };"
               " int main() { struct Point p; p.x = 5; p.y = 10; return p.x + p.y; }")
        self.assertEqual(self._exit_code(src), 15)

    def test_struct_member_assignment(self):
        src = ("struct Pair { int a; int b; };"
               " int main() { struct Pair q; q.a = 3; q.b = 7; return q.a * q.b; }")
        self.assertEqual(self._exit_code(src), 21)

    def test_switch_basic(self):
        src = ("int main() { int x = 2; int r = 0;"
               " switch (x) { case 1: r = 10; break; case 2: r = 20; break; case 3: r = 30; break; }"
               " return r; }")
        self.assertEqual(self._exit_code(src), 20 % 256)

    def test_switch_with_break(self):
        src = ("int main() { int x = 2; int r = 0;"
               " switch (x) { case 1: r = 10; break; case 2: r = 20; break; case 3: r = 30; break; }"
               " return r; }")
        self.assertEqual(self._exit_code(src), 20)

    def test_switch_default(self):
        src = ("int main() { int x = 99; int r = 0;"
               " switch (x) { case 1: r = 10; default: r = 99; }"
               " return r; }")
        self.assertEqual(self._exit_code(src), 99)

    def test_switch_fallthrough(self):
        src = ("int main() { int x = 1; int r = 0;"
               " switch (x) { case 1: r = r + 1; case 2: r = r + 10; case 3: r = r + 100; }"
               " return r; }")
        self.assertEqual(self._exit_code(src), 111)

    def test_switch_fallthrough_with_break(self):
        src = ("int main() { int x = 1; int r = 0;"
               " switch (x) { case 1: r = r + 1; break; case 2: r = r + 10; case 3: r = r + 100; }"
               " return r; }")
        self.assertEqual(self._exit_code(src), 1)

    def test_pointer_basic(self):
        src = "int main() { int x = 42; int *p = &x; return *p; }"
        self.assertEqual(self._exit_code(src), 42)

    def test_pointer_write_through(self):
        src = "int main() { int x = 0; int *p = &x; *p = 99; return x; }"
        self.assertEqual(self._exit_code(src), 99)

    def test_pointer_addrof_and_deref(self):
        src = ("int main() { int a = 10; int b = 20;"
               " int *pa = &a; int *pb = &b;"
               " return *pa + *pb; }")
        self.assertEqual(self._exit_code(src), 30)

    def test_pointer_modify_multiple(self):
        src = ("int main() { int x = 5; int y = 10;"
               " int *p = &x; *p = *p + 1;"
               " p = &y; *p = *p + 1;"
               " return x + y; }")
        self.assertEqual(self._exit_code(src), 17)

    def test_pointer_in_function(self):
        src = ("int set(int *p, int v) { *p = v; return 0; }"
               " int main() { int x = 0; set(&x, 77); return x; }")
        self.assertEqual(self._exit_code(src), 77)

    def test_pointer_loop(self):
        src = ("int main() { int a = 10; int b = 20; int c = 30;"
               " int *pa = &a; int *pb = &b; int *pc = &c;"
               " return *pa + *pb + *pc; }")
        self.assertEqual(self._exit_code(src), 60)

    def test_pointer_reassign(self):
        src = ("int main() { int a = 1; int b = 2;"
               " int *p = &a; p = &b; return *p; }")
        self.assertEqual(self._exit_code(src), 2)

    def test_array_basic(self):
        src = "int main() { int a[3]; a[0] = 10; a[1] = 20; a[2] = 30; return a[0] + a[1] + a[2]; }"
        self.assertEqual(self._exit_code(src), 60)

    def test_array_read_write(self):
        src = "int main() { int a[5]; a[0] = 1; a[4] = 99; return a[0] + a[4]; }"
        self.assertEqual(self._exit_code(src), 100)

    def test_array_loop_sum(self):
        src = ("int main() { int a[5]; int i;"
               " for (i = 0; i < 5; i = i + 1) a[i] = i + 1;"
               " int s = 0; for (i = 0; i < 5; i = i + 1) s = s + a[i];"
               " return s; }")
        self.assertEqual(self._exit_code(src), 15)

    def test_array_index_expression(self):
        src = ("int main() { int a[3]; a[0] = 5; a[1] = 10;"
               " int i = 1; return a[i] - a[i - 1]; }")
        self.assertEqual(self._exit_code(src), 5)

    def test_array_modify_in_loop(self):
        src = ("int main() { int a[4]; int i;"
               " for (i = 0; i < 4; i = i + 1) a[i] = i * 2;"
               " for (i = 0; i < 4; i = i + 1) a[i] = a[i] + 1;"
               " return a[0] + a[1] + a[2] + a[3]; }")
        self.assertEqual(self._exit_code(src), 16)


if __name__ == "__main__":
    unittest.main()
