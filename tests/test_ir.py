"""Stage 4 tests: IR generation — three-address code.

Run: python3 -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from smgcc.cgrammar import load_c
from smgcc.ir import IRBuilder, ir_to_string


class IRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_c()
        cls.builder = IRBuilder()

    def _ir(self, src: str) -> list:
        ast = self.g.parse(src)
        return self.builder.build(ast)

    def _has_op(self, ir: list, op: str) -> bool:
        return any(inst[0] == op for inst in ir)

    def test_minimal_function(self):
        ir = self._ir("int main() { return 0; }")
        self.assertTrue(self._has_op(ir, "func_start"))
        self.assertTrue(self._has_op(ir, "func_end"))
        self.assertTrue(self._has_op(ir, "const"))
        self.assertTrue(self._has_op(ir, "ret"))

    def test_variable_declaration(self):
        ir = self._ir("int main() { int x = 5; return x; }")
        self.assertTrue(self._has_op(ir, "copy"))

    def test_binary_expression(self):
        ir = self._ir("int main() { return 2 + 3; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("add", ops)

    def test_binary_precedence(self):
        ir = self._ir("int main() { return 2 + 3 * 4; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("mul", ops)
        self.assertIn("add", ops)

    def test_comparison(self):
        ir = self._ir("int main() { return 1 < 2; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("lt", ops)

    def test_negation(self):
        ir = self._ir("int main() { return -5; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("neg", ops)

    def test_logical_not(self):
        ir = self._ir("int main() { return !1; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("not", ops)

    def test_if_statement(self):
        ir = self._ir("int main() { if (1) return 1; return 0; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("jumpz", ops)
        self.assertIn("label", ops)

    def test_if_else_statement(self):
        ir = self._ir("int main() { if (1) return 1; else return 2; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("jumps", ops)

    def test_while_loop(self):
        ir = self._ir("int main() { while (1) { } }")
        ops = [inst[0] for inst in ir]
        self.assertIn("label", ops)
        self.assertIn("jumpz", ops)
        self.assertIn("jumps", ops)

    def test_for_loop(self):
        ir = self._ir("int main() { for (int i = 0; i < 10; i = i + 1) { } }")
        ops = [inst[0] for inst in ir]
        self.assertIn("label", ops)
        self.assertIn("jumpz", ops)

    def test_function_call(self):
        ir = self._ir("int add(int a, int b) { return a + b; } int main() { return add(1, 2); }")
        ops = [inst[0] for inst in ir]
        self.assertIn("param", ops)
        self.assertIn("call", ops)

    def test_assignment(self):
        ir = self._ir("int main() { int x = 1; x = 2; return x; }")
        copies = [inst for inst in ir if inst[0] == "copy"]
        self.assertTrue(len(copies) >= 2)

    def test_ir_to_string(self):
        ir = self._ir("int main() { return 1; }")
        s = ir_to_string(ir)
        self.assertIn("func", s)
        self.assertIn("ret", s)

    def test_multiple_functions(self):
        ir = self._ir("int f() { return 1; } int main() { return f(); }")
        func_starts = [inst for inst in ir if inst[0] == "func_start"]
        self.assertEqual(len(func_starts), 2)

    def test_nested_blocks(self):
        ir = self._ir("int main() { int x = 0; { int y = 1; } return x; }")
        copies = [inst for inst in ir if inst[0] == "copy"]
        self.assertTrue(len(copies) >= 2)

    def test_break_continue(self):
        ir = self._ir("int main() { for (int i = 0; i < 10; i = i + 1) { if (i == 5) break; continue; } return 0; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("break", ops)
        self.assertIn("continue", ops)

    def test_address_of(self):
        ir = self._ir("int main() { int x = 5; int *p = &x; return *p; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("addr", ops)

    def test_dereference(self):
        ir = self._ir("int main() { int x = 5; int *p = &x; return *p; }")
        ops = [inst[0] for inst in ir]
        self.assertIn("deref", ops)


if __name__ == "__main__":
    unittest.main()
