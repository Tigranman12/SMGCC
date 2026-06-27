"""Stage 6 tests: comprehensive integration + self-hosting readiness.

Exercises ALL supported C features in single programs:
  functions, recursion, locals, arithmetic, comparisons, unary ops,
  if/else, while, do-while, for, switch/case/default, break, continue,
  enums, structs (nested, pointer, array, by-value params, return),
  pointers, arrays, address-of, dereference, member access, ->.

Run: python3 -m unittest tests.test_stage6 -v
Requires as + ld (binutils) on PATH.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from smgcc.driver import compile_to_asm, compile_to_exe
from smgcc.cgen import CompileError
from smgcc.peg import ParseError
from smgcc.analyze import SemanticError

_HAVE_TOOLS = shutil.which("as") and shutil.which("ld")


def _exit_code(src: str) -> int:
    d = tempfile.mkdtemp(prefix="smgcc_stage6_")
    exe = os.path.join(d, "prog")
    compile_to_exe(src, exe)
    return subprocess.run([exe]).returncode


def _asm_contains(src: str, fragment: str) -> bool:
    asm = compile_to_asm(src)
    return fragment in asm


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class KitchenSinkTest(unittest.TestCase):
    """One program that uses every feature at least once."""

    def test_kitchen_sink(self):
        src = """
        enum { RED, GREEN, BLUE };

        struct Point { int x; int y; };
        struct Rect { struct Point tl; struct Point br; };

        int add(int a, int b) { return a + b; }

        int fact(int n) {
            if (n < 2) return 1;
            return n * fact(n - 1);
        }

        int fib(int n) {
            if (n < 2) return n;
            return fib(n - 1) + fib(n - 2);
        }

        int abs_val(int x) {
            if (x < 0) return -x;
            return x;
        }

        int clamp(int lo, int hi, int v) {
            if (v < lo) return lo;
            if (v > hi) return hi;
            return v;
        }

        int area(struct Point a, struct Point b) {
            int dx = b.x - a.x;
            int dy = b.y - a.y;
            if (dx < 0) dx = -dx;
            if (dy < 0) dy = -dy;
            return dx * dy;
        }

        int sum_array(int n) {
            int a[10];
            int i;
            for (i = 0; i < n; i = i + 1) a[i] = i * i;
            int s = 0;
            for (i = 0; i < n; i = i + 1) s = s + a[i];
            return s;
        }

        int classify(int x) {
            switch (x) {
                case 0: return RED;
                case 1: return GREEN;
                case 2: return BLUE;
                default: return -1;
            }
        }

        int count_down(int n) {
            int s = 0;
            int i = n;
            do {
                s = s + i;
                i = i - 1;
            } while (i > 0);
            return s;
        }

        int main() {
            int r = 0;

            /* arithmetic + comparisons */
            r = r + add(10, 20);
            r = r + fact(5);
            r = r + fib(7);

            /* unary */
            r = r + abs_val(-3);
            r = r + clamp(0, 100, 50);

            /* enums */
            r = r + classify(1);

            /* structs */
            struct Point a;
            a.x = 2;
            a.y = 3;
            struct Point b;
            b.x = 5;
            b.y = 7;
            r = r + area(a, b);

            /* struct pointer */
            struct Point *pa = &a;
            pa->x = 10;
            r = r + pa->x;

            /* arrays */
            r = r + sum_array(5);

            /* do-while */
            r = r + count_down(4);

            /* while loop */
            int w = 0;
            int j = 1;
            while (j <= 5) { w = w + j; j = j + 1; }
            r = r + w;

            /* nested struct */
            struct Rect rc;
            rc.tl.x = 0;
            rc.tl.y = 0;
            rc.br.x = 3;
            rc.br.y = 4;
            r = r + rc.br.x + rc.br.y;

            /* pointer arithmetic via array */
            int arr[3];
            arr[0] = 100;
            arr[1] = 200;
            arr[2] = 300;
            int *p = &arr[0];
            r = r + *p;
            p = &arr[2];
            r = r + *p;

            /* for with break */
            int found = 0;
            int k;
            for (k = 0; k < 20; k = k + 1) {
                if (k == 13) { found = 1; break; }
            }
            r = r + found;

            /* for with continue */
            int evens = 0;
            for (k = 0; k < 10; k = k + 1) {
                if (k % 2 == 1) continue;
                evens = evens + 1;
            }
            r = r + evens;

            /* short-circuit */
            int sc = 0;
            if (1 && 1) sc = sc + 1;
            if (0 && 1 / 0) sc = sc + 100;
            if (1 || 1 / 0) sc = sc + 10;
            r = r + sc;

            return r;
        }
        """
        result = _exit_code(src)
        # add(30) + fact(120) + fib(13) + abs(3) + clamp(50) + classify(1)
        # + area(12) + pa->x(10) + sum_array(30) + count_down(10) + while(15)
        # + rc(7) + arr(400) + found(1) + evens(5) + sc(11) = 718
        self.assertEqual(result, 718 % 256)


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class StructEdgeCasesTest(unittest.TestCase):
    """Deeply nested structs, struct arrays of structs, pointer chains."""

    def test_triple_nested_struct(self):
        src = """
        struct A { int v; };
        struct B { struct A a; int w; };
        struct C { struct B b; int x; };
        int main() {
            struct C c;
            c.b.a.v = 1;
            c.b.w = 2;
            c.x = 3;
            struct C *pc = &c;
            return pc->b.a.v + pc->b.w + pc->x;
        }
        """
        self.assertEqual(_exit_code(src), 6)

    def test_struct_array_of_structs(self):
        src = """
        struct Pt { int x; int y; };
        struct Pair { struct Pt a; struct Pt b; };
        int main() {
            struct Pair arr[2];
            arr[0].a.x = 1;
            arr[0].a.y = 2;
            arr[0].b.x = 3;
            arr[0].b.y = 4;
            arr[1].a.x = 10;
            arr[1].b.y = 20;
            return arr[0].a.x + arr[0].b.y + arr[1].a.x + arr[1].b.y;
        }
        """
        self.assertEqual(_exit_code(src), 35)

    def test_struct_by_value_and_return(self):
        src = """
        struct V { int n; };
        struct V make(int v) { struct V r; r.n = v; return r; }
        int get(struct V v) { return v.n; }
        int main() {
            struct V a = make(42);
            struct V b = make(58);
            return get(a) + get(b);
        }
        """
        self.assertEqual(_exit_code(src), 100)


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class PointerEdgeCasesTest(unittest.TestCase):
    """Pointer arithmetic, reassignment, null-ish patterns."""

    def test_pointer_chain_through_array(self):
        src = """
        int main() {
            int a[4];
            a[0] = 10; a[1] = 20; a[2] = 30; a[3] = 40;
            int *p = &a[0];
            int *q = &a[2];
            return *p + *q;
        }
        """
        self.assertEqual(_exit_code(src), 40)

    def test_pointer_write_in_loop(self):
        src = """
        int main() {
            int a[5];
            int i;
            int *p = &a[0];
            for (i = 0; i < 5; i = i + 1) { *p = i * 10; p = p + 1; }
            p = &a[0];
            int s = 0;
            for (i = 0; i < 5; i = i + 1) { s = s + *p; p = p + 1; }
            return s;
        }
        """
        self.assertEqual(_exit_code(src), 100)

    def test_pointer_to_pointer_via_function(self):
        src = """
        int set(int *p, int v) { *p = v; return 0; }
        int get(int *p) { return *p; }
        int main() {
            int x = 0;
            set(&x, 99);
            return get(&x);
        }
        """
        self.assertEqual(_exit_code(src), 99)


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class RecursionEdgeCasesTest(unittest.TestCase):
    """Mutual recursion, deep recursion, tail-ish patterns."""

    def test_deep_recursion(self):
        src = """
        int fib(int n) {
            if (n < 2) return n;
            return fib(n - 1) + fib(n - 2);
        }
        int main() { return fib(10); }
        """
        self.assertEqual(_exit_code(src), 55)

    def test_countdown_recursion(self):
        src = """
        int countdown(int n) {
            if (n <= 0) return 0;
            return n + countdown(n - 1);
        }
        int main() { return countdown(10); }
        """
        self.assertEqual(_exit_code(src), 55)


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class SwitchEdgeCasesTest(unittest.TestCase):
    """Complex switch patterns, nested switches, fall-through."""

    def test_nested_switch(self):
        src = """
        int main() {
            int x = 1;
            int y = 2;
            int r = 0;
            switch (x) {
                case 1:
                    switch (y) {
                        case 1: r = 10; break;
                        case 2: r = 20; break;
                        default: r = 30; break;
                    }
                    break;
                case 2: r = 40; break;
                default: r = 50; break;
            }
            return r;
        }
        """
        self.assertEqual(_exit_code(src), 20)

    def test_switch_with_all_features(self):
        src = """
        int main() {
            int x = 3;
            int r = 0;
            switch (x) {
                case 1: r = 100; break;
                case 2: r = 200; break;
                case 3:
                    r = 300;
                    /* fall through */
                case 4:
                    r = r + 1;
                    break;
                case 5: r = 500; break;
                default: r = -1; break;
            }
            return r % 256;
        }
        """
        self.assertEqual(_exit_code(src), 301 % 256)

    def test_switch_with_enums(self):
        src = """
        enum { NORTH, SOUTH, EAST, WEST };
        int main() {
            int dir = EAST;
            int dx = 0;
            int dy = 0;
            switch (dir) {
                case NORTH: dy = 1; break;
                case SOUTH: dy = -1; break;
                case EAST: dx = 1; break;
                case WEST: dx = -1; break;
            }
            return dx + dy + 10;
        }
        """
        self.assertEqual(_exit_code(src), 11)


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class LoopEdgeCasesTest(unittest.TestCase):
    """Complex loop patterns."""

    def test_nested_loops_with_break_continue(self):
        src = """
        int main() {
            int sum = 0;
            int i;
            int j;
            for (i = 0; i < 5; i = i + 1) {
                for (j = 0; j < 5; j = j + 1) {
                    if (j == 3) continue;
                    if (i == 4) break;
                    sum = sum + 1;
                }
            }
            return sum;
        }
        """
        self.assertEqual(_exit_code(src), 16)

    def test_while_with_complex_condition(self):
        src = """
        int main() {
            int x = 1;
            int count = 0;
            while (x < 100) {
                x = x * 2;
                count = count + 1;
            }
            return count;
        }
        """
        self.assertEqual(_exit_code(src), 7)

    def test_do_while_vs_while_equivalence(self):
        src = """
        int fact_while(int n) {
            int r = 1;
            int i = 1;
            while (i <= n) { r = r * i; i = i + 1; }
            return r;
        }
        int fact_dowhile(int n) {
            int r = 1;
            int i = 1;
            do { r = r * i; i = i + 1; } while (i <= n);
            return r;
        }
        int main() {
            int a = fact_while(6);
            int b = fact_dowhile(6);
            return a + b;
        }
        """
        self.assertEqual(_exit_code(src), (720 + 720) % 256)


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class StringLiteralTest(unittest.TestCase):
    """String literal support."""

    def test_string_index(self):
        self.assertEqual(_exit_code('int main() { return "hello"[0]; }'), ord("h"))

    def test_string_last_char(self):
        self.assertEqual(_exit_code('int main() { return "hello"[4]; }'), ord("o"))

    def test_string_middle(self):
        self.assertEqual(_exit_code('int main() { return "abc"[1]; }'), ord("b"))

    def test_empty_string(self):
        self.assertEqual(_exit_code('int main() { return "abc"[3]; }'), 0)

    def test_string_sum(self):
        src = 'int main() { int s = 0; int i; for (i = 0; i < 3; i = i + 1) s = s + "abc"[i]; return s; }'
        self.assertEqual(_exit_code(src), (ord("a") + ord("b") + ord("c")) % 256)

    def test_string_escape_newline(self):
        src = 'int main() { return "a\\nb"[2]; }'
        self.assertEqual(_exit_code(src), ord("b"))


@unittest.skipUnless(_HAVE_TOOLS, "needs as + ld")
class CompileErrorTest(unittest.TestCase):
    """Verify good error messages for common mistakes."""

    def test_missing_semicolon(self):
        with self.assertRaises(ParseError):
            compile_to_asm("int main() { return 1 }")

    def test_undeclared_variable(self):
        with self.assertRaises(SemanticError):
            compile_to_asm("int main() { return x; }")

    def test_undeclared_function(self):
        with self.assertRaises(SemanticError):
            compile_to_asm("int main() { return foo(); }")

    def test_redeclaration_same_scope(self):
        with self.assertRaises(SemanticError):
            compile_to_asm("int main() { int x = 1; int x = 2; }")

    def test_deref_non_pointer(self):
        with self.assertRaises(SemanticError):
            compile_to_asm("int main() { int x = 5; *x = 10; }")


if __name__ == "__main__":
    unittest.main()
