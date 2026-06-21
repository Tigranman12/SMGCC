"""Intermediate Representation — Stage 4.

Flattens the AST into linear three-address code. Each instruction has at
most three operands. The IR is designed to be easy to translate into
x86-64 assembly.

IR Instruction Format:
    (op, dst, src1, src2)

Where:
    op     - operation name (const, copy, add, sub, mul, div, mod,
             eq, ne, lt, gt, le, ge, neg, not, jumps, jumpz, jumpnz,
             call, ret, param, label, func_start, func_end)
    dst    - destination register/variable (or None)
    src1   - first source operand (or None)
    src2   - second source operand (or None)

Example:
    int x = 2 + 3;
    becomes:
        ('const', 't1', 2, None)
        ('const', 't2', 3, None)
        ('add', 't3', 't1', 't2')
        ('copy', 'x', 't3', None)
"""


class IRBuilder:
    """Builds IR instructions from an AST."""
    def __init__(self):
        self.instructions = []
        self.temp_counter = 0
        self.label_counter = 0
        self.current_func = None

    def new_temp(self) -> str:
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def new_label(self, prefix: str = "L") -> str:
        self.label_counter += 1
        return f"{prefix}{self.label_counter}"

    def emit(self, op: str, dst=None, src1=None, src2=None):
        self.instructions.append((op, dst, src1, src2))

    def build(self, ast: tuple) -> list:
        """Build IR from a program AST. Returns list of instructions."""
        self.instructions = []
        self.temp_counter = 0
        self.label_counter = 0

        tag = ast[0]
        assert tag == "program"

        for func in ast[1]:
            self.gen_func(func)

        return self.instructions

    def gen_func(self, node):
        _, name, params, body = node
        self.current_func = name
        self.emit("func_start", name, params, None)
        self.gen_stmt(body)
        self.emit("func_end", name, None, None)
        self.current_func = None

    def gen_stmt(self, node):
        tag = node[0]

        if tag == "block":
            for stmt in node[1]:
                self.gen_stmt(stmt)

        elif tag == "decl":
            name = node[1]
            if node[2] is not None:
                val = self.gen_expr(node[2])
                self.emit("copy", name, val, None)

        elif tag == "ptrdecl":
            name = node[1]
            if node[2] is not None:
                val = self.gen_expr(node[2])
                self.emit("copy", name, val, None)

        elif tag == "arraydecl":
            # array declaration - just emit the size as metadata
            name = node[1]
            if node[2][0] == "num":
                self.emit("array_decl", name, node[2][1], None)

        elif tag == "ret":
            val = self.gen_expr(node[1])
            self.emit("ret", None, val, None)

        elif tag == "if":
            cond = self.gen_expr(node[1])
            else_label = self.new_label("else")
            end_label = self.new_label("endif")
            self.emit("jumpz", else_label, cond, None)
            self.gen_stmt(node[2])
            if node[3] is not None:
                self.emit("jumps", end_label, None, None)
                self.emit("label", else_label, None, None)
                self.gen_stmt(node[3])
            else:
                self.emit("label", else_label, None, None)
            self.emit("label", end_label, None, None)

        elif tag == "while":
            beg_label = self.new_label("while")
            end_label = self.new_label("wend")
            self.emit("label", beg_label, None, None)
            cond = self.gen_expr(node[1])
            self.emit("jumpz", end_label, cond, None)
            self.gen_stmt(node[2])
            self.emit("jumps", beg_label, None, None)
            self.emit("label", end_label, None, None)

        elif tag == "for":
            self.emit("label_begin_scope", None, None, None)
            init, test, step, body = node[1], node[2], node[3], node[4]
            if init is not None:
                self.gen_stmt(init)
            beg_label = self.new_label("for")
            cont_label = self.new_label("forcont")
            end_label = self.new_label("forend")
            self.emit("label", beg_label, None, None)
            if test is not None:
                cond = self.gen_expr(test)
                self.emit("jumpz", end_label, cond, None)
            self.gen_stmt(body)
            self.emit("label", cont_label, None, None)
            if step is not None:
                self.gen_expr(step)
            self.emit("jumps", beg_label, None, None)
            self.emit("label", end_label, None, None)
            self.emit("label_end_scope", None, None, None)

        elif tag == "break":
            self.emit("break", None, None, None)

        elif tag == "continue":
            self.emit("continue", None, None, None)

        elif tag == "exprstmt":
            self.gen_expr(node[1])

    def gen_expr(self, node) -> str:
        """Generate IR for an expression. Returns the temp holding the result."""
        tag = node[0]

        if tag == "num":
            dst = self.new_temp()
            self.emit("const", dst, node[1], None)
            return dst

        elif tag == "var":
            return node[1]

        elif tag == "assign":
            val = self.gen_expr(node[2])
            self.emit("copy", node[1], val, None)
            return node[1]

        elif tag == "bin":
            left = self.gen_expr(node[2])
            right = self.gen_expr(node[3])
            dst = self.new_temp()
            op = node[1]
            op_map = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod",
                      "==": "eq", "!=": "ne", "<": "lt", ">": "gt", "<=": "le", ">=": "ge"}
            self.emit(op_map[op], dst, left, right)
            return dst

        elif tag == "un":
            op = node[1]
            val = self.gen_expr(node[2])
            dst = self.new_temp()
            if op == "-":
                self.emit("neg", dst, val, None)
            elif op == "&":
                self.emit("addr", dst, val, None)
            elif op == "*":
                self.emit("deref", dst, val, None)
            else:
                self.emit("not", dst, val, None)
            return dst

        elif tag == "call":
            fname = node[1]
            args = node[2]
            # Evaluate args in reverse order for stack
            arg_temps = []
            for arg in reversed(args):
                t = self.gen_expr(arg)
                arg_temps.append(t)
            arg_temps.reverse()
            # Emit param instructions
            for at in arg_temps:
                self.emit("param", None, at, None)
            dst = self.new_temp()
            self.emit("call", dst, fname, len(args))
            return dst

        elif tag == "subscript":
            # ('subscript', array_expr, index_expr)
            arr = self.gen_expr(node[1])
            idx = self.gen_expr(node[2])
            dst = self.new_temp()
            self.emit("subscript", dst, arr, idx)
            return dst

        elif tag == "logor":
            # Short-circuit: if left is true, result is 1; else result is right
            left = self.gen_expr(node[1])
            dst = self.new_temp()
            true_label = self.new_label("ortrue")
            end_label = self.new_label("orend")
            self.emit("jumpnz", true_label, left, None)
            right = self.gen_expr(node[2])
            self.emit("copy", dst, right, None)
            self.emit("jumps", end_label, None, None)
            self.emit("label", true_label, None, None)
            self.emit("const", dst, 1, None)
            self.emit("label", end_label, None, None)
            return dst

        elif tag == "logand":
            # Short-circuit: if left is false, result is 0; else result is right
            left = self.gen_expr(node[1])
            dst = self.new_temp()
            false_label = self.new_label("andfalse")
            end_label = self.new_label("andend")
            self.emit("jumpz", false_label, left, None)
            right = self.gen_expr(node[2])
            self.emit("copy", dst, right, None)
            self.emit("jumps", end_label, None, None)
            self.emit("label", false_label, None, None)
            self.emit("const", dst, 0, None)
            self.emit("label", end_label, None, None)
            return dst

        raise RuntimeError(f"unknown expression: {tag}")


def ir_to_string(instructions: list) -> str:
    """Pretty-print IR instructions for debugging."""
    lines = []
    for inst in instructions:
        op, dst, src1, src2 = inst
        if op == "label":
            lines.append(f"{dst}:")
        elif op == "func_start":
            params = ", ".join(src1) if src1 else ""
            lines.append(f"func {dst}({params}) {{")
        elif op == "func_end":
            lines.append("}")
        elif src2 is not None:
            lines.append(f"  {dst} = {src1} {op} {src2}")
        elif src1 is not None and dst is not None:
            if op in ("const", "copy"):
                lines.append(f"  {dst} = {src1}")
            elif op in ("neg", "not", "deref", "addr"):
                lines.append(f"  {dst} = {op} {src1}")
            elif op in ("jumps", "jumpz", "jumpnz"):
                lines.append(f"  {op} {dst} if {src1}")
            elif op == "call":
                lines.append(f"  {dst} = call {src1}({src2})")
            elif op == "param":
                lines.append(f"  param {dst}")
            elif op == "ret":
                lines.append(f"  return {src1}")
            else:
                lines.append(f"  {dst} = {op} {src1}")
        elif dst is not None:
            if op == "label_begin_scope":
                lines.append("  {")
            elif op == "label_end_scope":
                lines.append("  }")
            elif op == "break":
                lines.append("  break")
            elif op == "continue":
                lines.append("  continue")
            elif op == "param":
                lines.append(f"  param {dst}")
            else:
                lines.append(f"  {op} {dst}")
        else:
            lines.append(f"  {op}")
    return "\n".join(lines)
