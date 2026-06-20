"""x86-64 code generator — Stages 3-5 folded into one pass.

Strategy: a classic stack machine. Every expression computes its result into
%rax; binary ops push the left operand, compute the right, then combine. Locals
(params + declared vars) live in the stack frame at negative offsets from %rbp.

A light semantic check happens here too: using an undeclared variable is an
error. Output is GNU assembler (AT&T) text for a freestanding program — `_start`
calls main and turns its return value into the process exit code via syscall, so
no libc is needed and the linked binary is tiny.
"""

ARG_REGS = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]

_SETCC = {"==": "sete", "!=": "setne", "<": "setl",
          ">": "setg", "<=": "setle", ">=": "setge"}


class CompileError(Exception):
    pass


def _collect_locals(params, body):
    """All names that need a stack slot: params first, then every declared var."""
    names = list(params)

    def walk(n):
        if not isinstance(n, tuple):
            return
        tag = n[0]
        if tag == "decl":
            if n[1] not in names:
                names.append(n[1])
        elif tag == "block":
            for s in n[1]:
                walk(s)
        elif tag == "if":
            walk(n[2])
            walk(n[3])
        elif tag == "while":
            walk(n[2])

    walk(body)
    return names


class Gen:
    def __init__(self):
        self.out = []
        self.counter = 0
        self.off = {}
        self.epilogue = ""

    def emit(self, line):
        self.out.append(line)

    def label(self, prefix):
        self.counter += 1
        return f".L{prefix}{self.counter}"

    # -- top level -----------------------------------------------------------
    def gen_program(self, prog):
        self.emit("    .text")
        self.emit("    .globl _start")
        self.emit("_start:")
        self.emit("    call main")
        self.emit("    mov %rax, %rdi")     # exit code = main's return
        self.emit("    mov $60, %rax")      # SYS_exit
        self.emit("    syscall")
        for func in prog[1]:
            self.gen_func(func)
        return "\n".join(self.out) + "\n"

    def gen_func(self, func):
        _, name, params, body = func
        if len(params) > 6:
            raise CompileError(f"{name}: more than 6 parameters not supported")
        locals_ = _collect_locals(params, body)
        self.off = {nm: -8 * (i + 1) for i, nm in enumerate(locals_)}
        frame = ((8 * len(locals_)) + 15) // 16 * 16
        self.epilogue = self.label("ret_" + name)

        self.emit(f"{name}:")
        self.emit("    push %rbp")
        self.emit("    mov %rsp, %rbp")
        if frame:
            self.emit(f"    sub ${frame}, %rsp")
        for i, p in enumerate(params):
            self.emit(f"    mov {ARG_REGS[i]}, {self.off[p]}(%rbp)")
        self.gen_stmt(body)
        self.emit("    mov $0, %rax")        # default return value on fall-through
        self.emit(f"{self.epilogue}:")
        self.emit("    leave")
        self.emit("    ret")

    # -- statements ----------------------------------------------------------
    def gen_stmt(self, n):
        tag = n[0]
        if tag == "block":
            for s in n[1]:
                self.gen_stmt(s)
        elif tag == "decl":
            if n[2] is not None:
                self.gen_expr(n[2])
                self.emit(f"    mov %rax, {self.off[n[1]]}(%rbp)")
        elif tag == "exprstmt":
            self.gen_expr(n[1])
        elif tag == "ret":
            self.gen_expr(n[1])
            self.emit(f"    jmp {self.epilogue}")
        elif tag == "if":
            end = self.label("ifend")
            self.gen_expr(n[1])
            self.emit("    cmp $0, %rax")
            if n[3] is not None:
                els = self.label("else")
                self.emit(f"    je {els}")
                self.gen_stmt(n[2])
                self.emit(f"    jmp {end}")
                self.emit(f"{els}:")
                self.gen_stmt(n[3])
            else:
                self.emit(f"    je {end}")
                self.gen_stmt(n[2])
            self.emit(f"{end}:")
        elif tag == "while":
            beg = self.label("while")
            end = self.label("wend")
            self.emit(f"{beg}:")
            self.gen_expr(n[1])
            self.emit("    cmp $0, %rax")
            self.emit(f"    je {end}")
            self.gen_stmt(n[2])
            self.emit(f"    jmp {beg}")
            self.emit(f"{end}:")
        else:
            raise CompileError(f"cannot generate statement: {tag}")

    # -- expressions (result in %rax) ----------------------------------------
    def gen_expr(self, n):
        tag = n[0]
        if tag == "num":
            self.emit(f"    mov ${n[1]}, %rax")
        elif tag == "var":
            self.emit(f"    mov {self._slot(n[1])}, %rax")
        elif tag == "assign":
            self.gen_expr(n[2])
            self.emit(f"    mov %rax, {self._slot(n[1])}")
        elif tag == "un":
            self.gen_expr(n[2])
            if n[1] == "-":
                self.emit("    neg %rax")
            else:  # logical not
                self.emit("    cmp $0, %rax")
                self.emit("    sete %al")
                self.emit("    movzbq %al, %rax")
        elif tag == "bin":
            self.gen_expr(n[2])
            self.emit("    push %rax")
            self.gen_expr(n[3])
            self.emit("    mov %rax, %rcx")
            self.emit("    pop %rax")
            self._binop(n[1])
        elif tag == "call":
            args = n[2]
            if len(args) > 6:
                raise CompileError(f"{n[1]}: more than 6 arguments not supported")
            for a in args:
                self.gen_expr(a)
                self.emit("    push %rax")
            for i in range(len(args) - 1, -1, -1):
                self.emit(f"    pop {ARG_REGS[i]}")
            self.emit(f"    call {n[1]}")
        else:
            raise CompileError(f"cannot generate expression: {tag}")

    def _binop(self, op):
        # left in %rax, right in %rcx
        if op == "+":
            self.emit("    add %rcx, %rax")
        elif op == "-":
            self.emit("    sub %rcx, %rax")
        elif op == "*":
            self.emit("    imul %rcx, %rax")
        elif op in ("/", "%"):
            self.emit("    cqo")
            self.emit("    idiv %rcx")
            if op == "%":
                self.emit("    mov %rdx, %rax")
        elif op in _SETCC:
            self.emit("    cmp %rcx, %rax")
            self.emit(f"    {_SETCC[op]} %al")
            self.emit("    movzbq %al, %rax")
        else:
            raise CompileError(f"unknown operator: {op}")

    def _slot(self, name):
        if name not in self.off:
            raise CompileError(f"undeclared variable: {name!r}")
        return f"{self.off[name]}(%rbp)"


def generate(ast):
    """AST -> x86-64 assembly text."""
    return Gen().gen_program(ast)
