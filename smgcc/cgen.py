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


def _collect_locals(params, body, structs=None):
    """All names that need a stack slot: params first, then every declared var.
    Returns (names, array_sizes) where array_sizes maps array names to element count."""
    structs = structs or {}
    names = []
    array_sizes = {}
    for p in params:
        if isinstance(p, tuple) and p[0] == "*":
            names.append(p[1])
        else:
            names.append(p)

    def walk(n):
        if not isinstance(n, tuple):
            return
        tag = n[0]
        if tag == "decl":
            if n[1] not in names:
                names.append(n[1])
        elif tag == "ptrdecl":
            if n[1] not in names:
                names.append(n[1])
        elif tag == "arraydecl":
            if n[1] not in names:
                names.append(n[1])
                # Evaluate constant size (must be a literal for stack allocation)
                if n[2][0] == "num":
                    array_sizes[n[1]] = n[2][1]
                else:
                    array_sizes[n[1]] = 0  # non-constant size, handled at runtime
        elif tag == "struct_var":
            if n[2] not in names:
                names.append(n[2])
        elif tag == "block":
            for s in n[1]:
                walk(s)
        elif tag == "if":
            walk(n[2])
            walk(n[3])
        elif tag == "while":
            walk(n[2])
        elif tag == "for":
            if n[1] is not None:
                walk(n[1])
            walk(n[4])
        elif tag == "do_while":
            walk(n[1])
        elif tag == "switch":
            for case in n[2]:
                for s in case[2]:
                    walk(s)
            if n[3] is not None:
                for s in n[3][1]:
                    walk(s)

    walk(body)
    return names, array_sizes


class Gen:
    def __init__(self, enum_values=None, structs=None):
        self.out = []
        self.counter = 0
        self.off = {}
        self.epilogue = ""
        self.loops = []   # stack of (continue_label, break_label)
        self.enum_values = enum_values or {}
        self.structs = structs or {}
        self.var_types = {}  # maps variable name to its type string

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
            if func[0] == "func":
                self.gen_func(func)
        return "\n".join(self.out) + "\n"

    def gen_func(self, func):
        _, name, params, body = func
        if len(params) > 6:
            raise CompileError(f"{name}: more than 6 parameters not supported")
        locals_, array_sizes = _collect_locals(params, body)
        self.array_sizes = array_sizes
        # Compute stack offsets: arrays get extra space
        # Arrays occupy size*8 bytes; other vars occupy 8 bytes.
        # Allocate top-down: each var gets the lowest available address.
        self.off = {}
        offset = 0
        for nm in locals_:
            if nm in array_sizes and array_sizes[nm] > 0:
                size = array_sizes[nm]
                offset -= size * 8
                self.off[nm] = offset  # base of array (lowest address)
            else:
                offset -= 8
                self.off[nm] = offset
        raw = -offset  # total bytes used
        # Round frame up to next multiple of 8, then ensure frame ≡ 8 (mod 16).
        # This guarantees: after push %rbp + sub $frame, rsp ≡ 8 (mod 16),
        # so push (arg) before call lands at 0 mod 16.
        frame = ((raw + 7) // 8) * 8
        if frame % 16 == 0:
            frame += 8
        self.epilogue = self.label("ret_" + name)
        self.loops = []

        self.emit(f"{name}:")
        self.emit("    push %rbp")
        self.emit("    mov %rsp, %rbp")
        if frame:
            self.emit(f"    sub ${frame}, %rsp")
        for i, p in enumerate(params):
            pname = p[1] if isinstance(p, tuple) else p
            self.emit(f"    mov {ARG_REGS[i]}, {self.off[pname]}(%rbp)")
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
        elif tag == "ptrdecl":
            if n[2] is not None:
                self.gen_expr(n[2])
                self.emit(f"    mov %rax, {self.off[n[1]]}(%rbp)")
        elif tag == "arraydecl":
            # array declaration - space is allocated in frame, no init code needed
            pass
        elif tag == "struct_var":
            # struct declarations don't need codegen - space is allocated in frame
            # But we need to track the type for member access
            self.var_types[n[2]] = f"struct:{n[1]}"
            pass
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
            self.loops.append((beg, end))     # continue re-tests the condition
            self.gen_stmt(n[2])
            self.loops.pop()
            self.emit(f"    jmp {beg}")
            self.emit(f"{end}:")
        elif tag == "do_while":
            beg = self.label("dowhile")
            end = self.label("dowhileend")
            self.emit(f"{beg}:")
            self.loops.append((beg, end))     # continue jumps to condition check
            self.gen_stmt(n[1])
            self.loops.pop()
            self.gen_expr(n[2])
            self.emit("    cmp $0, %rax")
            self.emit(f"    jne {beg}")
            self.emit(f"{end}:")
        elif tag == "switch":
            end = self.label("switchend")
            val = self.gen_expr(n[1])
            self.emit("    push %rax")           # save switch value on stack
            cases = n[2]
            default = n[3]
            case_labels = [self.label("case") for _ in cases]
            body_labels = [self.label("cbody") for _ in cases]
            # compare and jump to case entry points
            for i, case in enumerate(cases):
                case_val = self.gen_expr(case[1])
                self.emit("    mov %rax, %rcx")
                self.emit("    mov (%rsp), %rax")
                self.emit("    cmp %rcx, %rax")
                self.emit(f"    je {case_labels[i]}")
            # fall to default or end
            if default is not None:
                self.emit(f"    jmp default{end}")
            else:
                self.emit(f"    jmp {end}")
            # case bodies (fall-through by default)
            self.loops.append((None, end))  # break exits switch
            for i, case in enumerate(cases):
                self.emit(f"{case_labels[i]}:")
                self.emit("    add $8, %rsp")    # pop saved value
                self.emit(f"    jmp {body_labels[i]}")
            # default body
            if default is not None:
                self.emit(f"default{end}:")
                self.emit("    add $8, %rsp")    # pop saved value
            # case bodies
            for i, case in enumerate(cases):
                self.emit(f"{body_labels[i]}:")
                for stmt in case[2]:
                    self.gen_stmt(stmt)
            if default is not None:
                self.emit(f"dflt{end}:")
                for stmt in default[1]:
                    self.gen_stmt(stmt)
            self.loops.pop()
            self.emit(f"{end}:")
        elif tag == "for":
            init, test, step, body = n[1], n[2], n[3], n[4]
            beg = self.label("for")
            cont = self.label("forcont")
            end = self.label("forend")
            if init is not None:
                self.gen_stmt(init)
            self.emit(f"{beg}:")
            if test is not None:
                self.gen_expr(test)
                self.emit("    cmp $0, %rax")
                self.emit(f"    je {end}")
            self.loops.append((cont, end))    # continue runs the step
            self.gen_stmt(body)
            self.loops.pop()
            self.emit(f"{cont}:")
            if step is not None:
                self.gen_expr(step)
            self.emit(f"    jmp {beg}")
            self.emit(f"{end}:")
        elif tag == "break":
            if not self.loops:
                raise CompileError("break outside loop")
            self.emit(f"    jmp {self.loops[-1][1]}")
        elif tag == "continue":
            if not self.loops:
                raise CompileError("continue outside loop")
            self.emit(f"    jmp {self.loops[-1][0]}")
        else:
            raise CompileError(f"cannot generate statement: {tag}")

    # -- expressions (result in %rax) ----------------------------------------
    def gen_expr(self, n):
        tag = n[0]
        if tag == "num":
            self.emit(f"    mov ${n[1]}, %rax")
        elif tag == "var":
            name = n[1]
            if name in self.enum_values:
                self.emit(f"    mov ${self.enum_values[name]}, %rax")
            else:
                self.emit(f"    mov {self._slot(name)}, %rax")
        elif tag == "un":
            op = n[1]
            if op == "&":
                # address-of: load effective address of variable
                inner = n[2]
                if isinstance(inner, tuple) and inner[0] == "var":
                    self.emit(f"    lea {self._slot(inner[1])}, %rax")
                else:
                    raise CompileError("address-of requires a variable")
            elif op == "*":
                # dereference: load value from address
                self.gen_expr(n[2])
                self.emit("    mov (%rax), %rax")
            elif op == "-":
                self.gen_expr(n[2])
                self.emit("    neg %rax")
            else:  # logical not
                self.gen_expr(n[2])
                self.emit("    cmp $0, %rax")
                self.emit("    sete %al")
                self.emit("    movzbq %al, %rax")
        elif tag == "member":
            # ('member', obj, member_name) - load struct member
            self._gen_member_addr(n[1], n[2])
            self.emit("    mov (%rax), %rax")
        elif tag == "subscript":
            # ('subscript', array_expr, index_expr) - load array element
            self._gen_subscript_addr(n[1], n[2])
            self.emit("    mov (%rax), %rax")
        elif tag == "assign":
            target = n[1]
            if isinstance(target, tuple) and target[0] == "member":
                # member assignment: obj.member = expr
                self._gen_member_addr(target[1], target[2])
                self.emit("    push %rax")
                self.gen_expr(n[2])
                self.emit("    pop %rcx")
                self.emit("    mov %rax, (%rcx)")
            elif isinstance(target, tuple) and target[0] == "un" and target[1] == "*":
                # pointer dereference assignment: *p = expr
                self.gen_expr(target[2])  # compute address
                self.emit("    push %rax")
                self.gen_expr(n[2])       # compute value
                self.emit("    pop %rcx")
                self.emit("    mov %rax, (%rcx)")
            elif isinstance(target, tuple) and target[0] == "subscript":
                # array subscript assignment: a[i] = expr
                self._gen_subscript_addr(target[1], target[2])
                self.emit("    push %rax")
                self.gen_expr(n[2])
                self.emit("    pop %rcx")
                self.emit("    mov %rax, (%rcx)")
            elif isinstance(target, tuple) and target[0] == "var":
                self.gen_expr(n[2])
                self.emit(f"    mov %rax, {self._slot(target[1])}")
            else:
                self.gen_expr(n[2])
                self.emit(f"    mov %rax, {self._slot(target)}")
        elif tag == "un":
            self.gen_expr(n[2])
            if n[1] == "-":
                self.emit("    neg %rax")
            else:  # logical not
                self.emit("    cmp $0, %rax")
                self.emit("    sete %al")
                self.emit("    movzbq %al, %rax")
        elif tag == "logand":
            false = self.label("andfalse")
            end = self.label("andend")
            self.gen_expr(n[1])
            self.emit("    cmp $0, %rax")
            self.emit(f"    je {false}")
            self.gen_expr(n[2])
            self.emit("    cmp $0, %rax")
            self.emit(f"    je {false}")
            self.emit("    mov $1, %rax")
            self.emit(f"    jmp {end}")
            self.emit(f"{false}:")
            self.emit("    mov $0, %rax")
            self.emit(f"{end}:")
        elif tag == "logor":
            true = self.label("ortrue")
            end = self.label("orend")
            self.gen_expr(n[1])
            self.emit("    cmp $0, %rax")
            self.emit(f"    jne {true}")
            self.gen_expr(n[2])
            self.emit("    cmp $0, %rax")
            self.emit(f"    jne {true}")
            self.emit("    mov $0, %rax")
            self.emit(f"    jmp {end}")
            self.emit(f"{true}:")
            self.emit("    mov $1, %rax")
            self.emit(f"{end}:")
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

    def _gen_member_addr(self, obj, member):
        """Generate code to load address of struct member into %rax.
        obj is a var node or variable name string, member is the member name string."""
        # Handle both node and string inputs
        if isinstance(obj, str):
            obj_name = obj
        elif isinstance(obj, tuple) and obj[0] == "var":
            obj_name = obj[1]
        else:
            raise CompileError("struct member access on non-variable")
        slot = self._slot(obj_name)
        # Find the struct type for this variable
        stype = self.var_types.get(obj_name, "")
        if not stype.startswith("struct:"):
            raise CompileError(f"cannot access member of non-struct variable '{obj_name}'")
        struct_name = stype[7:]  # remove "struct:" prefix
        if struct_name not in self.structs:
            raise CompileError(f"unknown struct type '{struct_name}'")
        members = self.structs[struct_name]
        if member not in members:
            raise CompileError(f"struct '{struct_name}' has no member '{member}'")
        # Compute offset: each member is 8 bytes (int)
        offset = members.index(member) * 8
        self.emit(f"    lea {slot}, %rax")
        if offset:
            self.emit(f"    add ${offset}, %rax")

    def _gen_subscript_addr(self, array_expr, index_expr):
        """Generate code to load address of array element into %rax.
        Computes: base_addr + index * 8."""
        # Get array variable name
        if isinstance(array_expr, tuple) and array_expr[0] == "var":
            arr_name = array_expr[1]
        elif isinstance(array_expr, str):
            arr_name = array_expr
        else:
            raise CompileError("array subscript on non-variable")
        slot = self._slot(arr_name)
        # Compute index
        self.gen_expr(index_expr)
        # Multiply index by 8 (element size)
        self.emit("    shl $3, %rax")
        # Add base address
        self.emit("    lea {slot}, %rcx".format(slot=slot))
        self.emit("    add %rcx, %rax")


def generate(ast, enum_values=None, structs=None):
    """AST -> x86-64 assembly text."""
    return Gen(enum_values, structs).gen_program(ast)
