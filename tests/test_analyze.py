"""Stage 3 tests: semantic analysis — symbol tables, type checking, scope validation.

Run: python3 -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from smgcc.cgrammar import load_c
from smgcc.analyze import analyze, SemanticError


class SemanticAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_c()

    def _analyze(self, src: str) -> dict:
        ast = self.g.parse(src)
        return analyze(ast)

    def test_minimal_function(self):
        t = self._analyze("int main() { return 0; }")
        self.assertIn("main", t["functions"])

    def test_undeclared_variable(self):
        with self.assertRaises(SemanticError) as ctx:
            self._analyze("int main() { return x; }")
        self.assertIn("undeclared", str(ctx.exception))

    def test_redeclaration(self):
        with self.assertRaises(SemanticError) as ctx:
            self._analyze("int main() { int x = 1; int x = 2; }")
        self.assertIn("redeclaration", str(ctx.exception))

    def test_redeclaration_across_scopes_ok(self):
        t = self._analyze("int main() { int x = 1; { int x = 2; } return x; }")
        self.assertIn("main", t["functions"])

    def test_if_scope(self):
        t = self._analyze("int main() { int x = 1; if (x) { int y = 2; } return x; }")
        self.assertIn("main", t["functions"])

    def test_while_scope(self):
        t = self._analyze("int main() { int x = 0; while (x < 10) { x = x + 1; } return x; }")
        self.assertIn("main", t["functions"])

    def test_for_scope(self):
        t = self._analyze("int main() { int s = 0; for (int i = 0; i < 10; i = i + 1) s = s + i; return s; }")
        self.assertIn("main", t["functions"])

    def test_function_call(self):
        t = self._analyze("int add(int a, int b) { return a + b; } int main() { return add(1, 2); }")
        self.assertIn("add", t["functions"])
        self.assertIn("main", t["functions"])

    def test_undeclared_function(self):
        with self.assertRaises(SemanticError) as ctx:
            self._analyze("int main() { return foo(1); }")
        self.assertIn("undeclared function", str(ctx.exception))

    def test_redeclare_function(self):
        with self.assertRaises(SemanticError) as ctx:
            self._analyze("int main() { return 0; } int main() { return 1; }")
        self.assertIn("redeclaration", str(ctx.exception))

    def test_assignment_undeclared(self):
        with self.assertRaises(SemanticError):
            self._analyze("int main() { x = 5; }")

    def test_declaration_with_init(self):
        t = self._analyze("int main() { int x = 5; return x; }")
        self.assertIn("main", t["functions"])

    def test_complex_function(self):
        src = """
        int fact(int n) {
            if (n < 2) return 1;
            return n * fact(n - 1);
        }
        int main() {
            return fact(5);
        }
        """
        t = self._analyze(src)
        self.assertIn("fact", t["functions"])
        self.assertIn("main", t["functions"])

    def test_pointer_declaration(self):
        t = self._analyze("int main() { int x = 5; int *p = &x; return *p; }")
        self.assertIn("main", t["functions"])

    def test_pointer_deref_type(self):
        t = self._analyze("int main() { int x = 5; int *p = &x; *p = 10; return x; }")
        self.assertIn("main", t["functions"])

    def test_pointer_undeclared_deref(self):
        with self.assertRaises(SemanticError):
            self._analyze("int main() { int *p = &x; }")

    def test_addrof_enum_constant(self):
        with self.assertRaises(SemanticError):
            self._analyze("enum { X }; int main() { int *p = &X; }")

    def test_deref_non_pointer(self):
        with self.assertRaises(SemanticError):
            self._analyze("int main() { int x = 5; *x = 10; }")


if __name__ == "__main__":
    unittest.main()
