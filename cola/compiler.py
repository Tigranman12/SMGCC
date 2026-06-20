"""COLA -> COLA-VM bytecode compiler.

Every expression compiles to a net stack effect of +1 (it leaves its result on
the stack), so top-level forms can be uniformly POPped. Special forms map to the
VM opcodes documented in cola_vm.c. Scoping: a function's parameters are the only
locals; any other name resolves to a global (the VM's bytecode closures do not
capture — see the limitation note in the README).
"""


class ColaCompileError(Exception):
    pass


class Program:
    """Accumulates instructions and a typed constant pool.

    code: list of [op_name, arg]
    consts: list of (kind, value) where kind in {'int','str','sym'}
    """
    def __init__(self):
        self.code = []
        self.consts = []

    def emit(self, op, arg=0):
        self.code.append([op, arg])
        return len(self.code) - 1

    def here(self):
        return len(self.code)

    def patch(self, idx, arg):
        self.code[idx][1] = arg

    def const(self, kind, value):
        for i, (k, v) in enumerate(self.consts):
            if k == kind and v == value:
                return i
        self.consts.append((kind, value))
        return len(self.consts) - 1


_ARITH = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}
_CMP = {"=": "EQ", "<": "LT", ">": "GT"}


class Compiler:
    def __init__(self):
        self.p = Program()
        self.scopes = []   # stack of parameter-name lists (innermost last)

    # -- entry ---------------------------------------------------------------
    def compile_program(self, forms):
        for form in forms:
            self.compile_expr(form)
            self.p.emit("POP")
        self.p.emit("HALT")
        return self.p

    # -- expressions ---------------------------------------------------------
    def compile_expr(self, node):
        tag = node[0]
        if tag == "int":
            self.p.emit("PUSH_INT", node[1])
        elif tag == "str":
            self.p.emit("PUSH_CONST", self.p.const("str", node[1]))
        elif tag == "sym":
            self._var(node[1])
        elif tag == "list":
            self._list(node[1])
        else:
            raise ColaCompileError(f"cannot compile node: {node!r}")

    def _var(self, name):
        if name == "true":
            self.p.emit("PUSH_TRUE")
        elif name == "false":
            self.p.emit("PUSH_FALSE")
        elif name == "nil":
            self.p.emit("PUSH_NIL")
        else:
            idx = self._local(name)
            if idx is not None:
                self.p.emit("PUSH_LOCAL", idx)
            else:
                self.p.emit("PUSH_GLOBAL", self.p.const("sym", name))

    def _local(self, name):
        if self.scopes and name in self.scopes[-1]:
            return self.scopes[-1].index(name)
        return None

    def _list(self, elems):
        if not elems:
            self.p.emit("PUSH_NIL")
            return
        head, args = elems[0], elems[1:]
        if head[0] == "sym":
            op = head[1]
            handler = _SPECIAL.get(op)
            if handler:
                handler(self, args)
                return
            if op in _ARITH:
                self._fold(_ARITH[op], args)
                return
            if op in _CMP:
                self._binary(_CMP[op], args)
                return
            if op == "<=":            # a <= b  ==  not (a > b)
                self._binary("GT", args)
                self.p.emit("NOT")
                return
            if op == ">=":            # a >= b  ==  not (a < b)
                self._binary("LT", args)
                self.p.emit("NOT")
                return
            # bare (f a b ...) — call a global closure by name
            self._var(op)
            for a in args:
                self.compile_expr(a)
            self.p.emit("CALL", len(args))
            return
        # ((expr) a b ...) — head is itself an expression producing a closure
        self.compile_expr(head)
        for a in args:
            self.compile_expr(a)
        self.p.emit("CALL", len(args))

    # -- special forms -------------------------------------------------------
    def _def(self, args):
        if len(args) != 2 or args[0][0] != "sym":
            raise ColaCompileError("def/set expects (name value)")
        self.compile_expr(args[1])
        self.p.emit("DUP")            # leave the value as the form's result
        self.p.emit("STORE_GLOBAL", self.p.const("sym", args[0][1]))

    def _if(self, args):
        cond, then = args[0], args[1]
        els = args[2] if len(args) > 2 else ("sym", "nil")
        self.compile_expr(cond)
        bf = self.p.emit("BRANCH_FALSE", 0)
        self.compile_expr(then)
        j = self.p.emit("JUMP", 0)
        self.p.patch(bf, self.p.here())
        self.compile_expr(els)
        self.p.patch(j, self.p.here())

    def _while(self, args):
        start = self.p.here()
        self.compile_expr(args[0])
        bf = self.p.emit("BRANCH_FALSE", 0)
        self._do(args[1:])
        self.p.emit("POP")
        self.p.emit("JUMP", start)
        self.p.patch(bf, self.p.here())
        self.p.emit("PUSH_NIL")

    def _do(self, args):
        if not args:
            self.p.emit("PUSH_NIL")
            return
        for e in args[:-1]:
            self.compile_expr(e)
            self.p.emit("POP")
        self.compile_expr(args[-1])

    def _fn(self, args):
        if not args or args[0][0] != "list":
            raise ColaCompileError("fn expects (params) body")
        params = [p[1] for p in args[0][1]]
        body = args[1:]
        self.p.emit("PUSH_INT", len(params))
        mc = self.p.emit("MAKE_CLOSURE", 0)
        j = self.p.emit("JUMP", 0)
        self.p.patch(mc, self.p.here())     # body_pc
        self.scopes.append(params)
        self._do(body)
        self.scopes.pop()
        self.p.emit("RETURN")
        self.p.patch(j, self.p.here())

    def _call(self, args):
        if not args:
            raise ColaCompileError("call expects a closure")
        self.compile_expr(args[0])
        for a in args[1:]:
            self.compile_expr(a)
        self.p.emit("CALL", len(args) - 1)

    def _send(self, args):
        if len(args) < 2 or args[1][0] != "sym":
            raise ColaCompileError("send expects (receiver message args...)")
        self.compile_expr(args[0])
        self.p.emit("PUSH_SYM", self.p.const("sym", args[1][1]))
        for a in args[2:]:
            self.compile_expr(a)
        self.p.emit("SEND", len(args) - 2)

    def _print(self, args):
        self.compile_expr(args[0])
        self.p.emit("PRINT")

    def _newline(self, args):
        self.p.emit("NEWLINE")
        self.p.emit("PUSH_NIL")

    def _not(self, args):
        self.compile_expr(args[0])
        self.p.emit("NOT")

    def _concat(self, args):
        self.compile_expr(args[0])
        self.compile_expr(args[1])
        self.p.emit("CONCAT")

    def _fold(self, opname, args):
        if not args:
            raise ColaCompileError(f"{opname} expects at least one argument")
        self.compile_expr(args[0])
        for a in args[1:]:
            self.compile_expr(a)
            self.p.emit(opname)

    def _binary(self, opname, args):
        if len(args) != 2:
            raise ColaCompileError(f"{opname} expects exactly 2 arguments")
        self.compile_expr(args[0])
        self.compile_expr(args[1])
        self.p.emit(opname)


_SPECIAL = {
    "def": Compiler._def, "set": Compiler._def,
    "if": Compiler._if, "while": Compiler._while, "do": Compiler._do,
    "fn": Compiler._fn, "call": Compiler._call, "send": Compiler._send,
    "print": Compiler._print, "newline": Compiler._newline, "nl": Compiler._newline,
    "not": Compiler._not, "concat": Compiler._concat,
}


def compile_forms(forms):
    """Compile a list of COLA forms into a Program."""
    return Compiler().compile_program(forms)
