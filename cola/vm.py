"""Reference COLA VM in Python — a faithful mirror of
LW_OS/phase8-cola-metal/cola/cola_vm.c.

Its only purpose is to *prove* that compiled bytecode produces the same output
the real on-OS VM would, without needing QEMU. Stack/frame/closure mechanics
match cola_vm.c instruction-for-instruction. `run()` returns captured output.
"""
from .opcodes import OPCODES


class _Sym:
    __slots__ = ("name",)
    def __init__(self, name):
        self.name = name

class _Str:
    __slots__ = ("data",)
    def __init__(self, data):
        self.data = data

class _Closure:
    __slots__ = ("body_pc", "n_params")
    def __init__(self, body_pc, n_params):
        self.body_pc = body_pc
        self.n_params = n_params

NIL = ("nil",)
TRUE = ("true",)
FALSE = ("false",)


def _truthy(v):
    return v is not FALSE and v is not NIL


def _reify(const):
    kind, value = const
    if kind == "int":
        return value
    if kind == "str":
        return _Str(value)
    if kind == "sym":
        return _Sym(value)
    raise ValueError(kind)


class Frame:
    __slots__ = ("return_pc", "base_sp", "n_locals")
    def __init__(self, return_pc, base_sp, n_locals):
        self.return_pc = return_pc
        self.base_sp = base_sp
        self.n_locals = n_locals


class ColaVM:
    def __init__(self, program):
        self.code = program.code
        self.consts = program.consts
        self.stack = []
        self.frames = [Frame(0, 0, 0)]
        self.globals = {}      # name -> value (mirrors global_syms/global_vals)
        self.pc = 0
        self.out = []

    # -- value printing (mirrors OP_PRINT in cola_vm.c) ----------------------
    def _render(self, v):
        if isinstance(v, int):
            return str(v)
        if v is NIL:
            return "nil"
        if v is TRUE:
            return "true"
        if v is FALSE:
            return "false"
        if isinstance(v, _Sym):
            return v.name
        if isinstance(v, _Str):
            return v.data
        if isinstance(v, _Closure):
            return "<closure>"
        return "<obj>"

    def run(self):
        code = self.code
        while self.pc < len(code):
            op, arg = code[self.pc]
            self.pc += 1
            m = getattr(self, "_op_" + op)
            if m(arg) == "halt":
                break
        return "".join(self.out)

    # -- opcode handlers -----------------------------------------------------
    def _op_NOP(self, a): pass
    def _op_HALT(self, a): return "halt"

    def _op_PUSH_INT(self, a): self.stack.append(a)
    def _op_PUSH_SYM(self, a): self.stack.append(_reify(self.consts[a]))
    def _op_PUSH_CONST(self, a): self.stack.append(_reify(self.consts[a]))
    def _op_PUSH_NIL(self, a): self.stack.append(NIL)
    def _op_PUSH_TRUE(self, a): self.stack.append(TRUE)
    def _op_PUSH_FALSE(self, a): self.stack.append(FALSE)
    def _op_POP(self, a): self.stack.pop()
    def _op_DUP(self, a): self.stack.append(self.stack[-1])

    def _op_PUSH_LOCAL(self, a):
        base = self.frames[-1].base_sp
        self.stack.append(self.stack[base + a])

    def _op_STORE_LOCAL(self, a):
        base = self.frames[-1].base_sp
        self.stack[base + a] = self.stack.pop()

    def _op_PUSH_GLOBAL(self, a):
        name = self.consts[a][1]
        self.stack.append(self.globals.get(name, NIL))

    def _op_STORE_GLOBAL(self, a):
        name = self.consts[a][1]
        self.globals[name] = self.stack.pop()

    def _op_ADD(self, a): b = self.stack.pop(); self.stack.append(self.stack.pop() + b)
    def _op_SUB(self, a): b = self.stack.pop(); self.stack.append(self.stack.pop() - b)
    def _op_MUL(self, a): b = self.stack.pop(); self.stack.append(self.stack.pop() * b)

    def _op_DIV(self, a):
        b = self.stack.pop(); x = self.stack.pop()
        self.stack.append(int(x / b) if b else NIL)

    def _op_MOD(self, a):
        b = self.stack.pop(); x = self.stack.pop()
        self.stack.append((x - int(x / b) * b) if b else NIL)

    def _op_EQ(self, a):
        b = self.stack.pop(); x = self.stack.pop()
        self.stack.append(TRUE if self._eq(x, b) else FALSE)

    def _op_LT(self, a):
        b = self.stack.pop(); x = self.stack.pop()
        self.stack.append(TRUE if x < b else FALSE)

    def _op_GT(self, a):
        b = self.stack.pop(); x = self.stack.pop()
        self.stack.append(TRUE if x > b else FALSE)

    def _op_NOT(self, a):
        v = self.stack.pop()
        self.stack.append(TRUE if not _truthy(v) else FALSE)

    @staticmethod
    def _eq(x, y):
        if isinstance(x, int) and isinstance(y, int):
            return x == y
        if isinstance(x, _Sym) and isinstance(y, _Sym):
            return x.name == y.name
        return x is y

    def _op_PRINT(self, a):
        self.out.append(self._render(self.stack[-1]))   # PRINT does not pop

    def _op_NEWLINE(self, a):
        self.out.append("\n")

    def _op_JUMP(self, a): self.pc = a
    def _op_BRANCH_FALSE(self, a):
        if not _truthy(self.stack.pop()):
            self.pc = a
    def _op_BRANCH_TRUE(self, a):
        if _truthy(self.stack.pop()):
            self.pc = a

    def _op_MAKE_CLOSURE(self, a):
        n_params = self.stack.pop()
        self.stack.append(_Closure(a, n_params))

    def _op_CALL(self, a):
        nargs = a
        sp = len(self.stack)
        closure = self.stack[sp - nargs - 1]
        if not isinstance(closure, _Closure):
            del self.stack[sp - nargs - 1:]
            self.stack.append(NIL)
            return
        args = self.stack[sp - nargs:sp]
        del self.stack[sp - nargs - 1:]           # pop args + closure
        self.frames.append(Frame(self.pc, len(self.stack), nargs))
        self.stack.extend(args)                    # args become locals 0..n-1
        self.pc = closure.body_pc

    def _op_RETURN(self, a):
        result = self.stack.pop()
        frame = self.frames.pop()
        del self.stack[frame.base_sp:]
        self.pc = frame.return_pc
        self.stack.append(result)

    def _op_SEND(self, a):
        nargs = a
        sp = len(self.stack)
        args = self.stack[sp - nargs:sp]
        selector = self.stack[sp - nargs - 1]
        receiver = self.stack[sp - nargs - 2]
        del self.stack[sp - nargs - 2:]
        self.stack.append(self._dispatch(receiver, selector, args))

    def _op_CONCAT(self, a):
        b = self.stack.pop(); x = self.stack.pop()
        self.stack.append(_Str(self._render(x) + self._render(b)))

    def _dispatch(self, receiver, selector, args):
        sel = selector.name if isinstance(selector, _Sym) else None
        if isinstance(receiver, int):
            if sel == "+": return receiver + args[0]
            if sel == "-": return receiver - args[0]
            if sel == "*": return receiver * args[0]
            if sel == "/": return int(receiver / args[0]) if args[0] else NIL
            if sel == "%": return (receiver % args[0]) if args[0] else NIL
            if sel == "=": return TRUE if receiver == args[0] else FALSE
            if sel == "<": return TRUE if receiver < args[0] else FALSE
            if sel == ">": return TRUE if receiver > args[0] else FALSE
            if sel == "print":
                self.out.append(str(receiver)); return receiver
        if isinstance(receiver, _Str):
            if sel == "print":
                self.out.append(receiver.data); return receiver
            if sel == "length":
                return len(receiver.data)
        return NIL


def run_program(program):
    """Compile-then-run helper: returns the program's printed output."""
    return ColaVM(program).run()
