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
        elif isinstance(p, tuple) and p[0] == "struct":
            names.append(p[2])
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
        elif tag == "structptrdecl":
            if n[2] not in names:
                names.append(n[2])
        elif tag == "structarraydecl":
            if n[2] not in names:
                names.append(n[2])
                # Struct array: size * member_count * 8 bytes per element
                if n[3][0] == "num":
                    array_sizes[n[2]] = n[3][1]
                else:
                    array_sizes[n[2]] = 0
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
        self.strings = []   # list of string literals (content, label)
        self.string_map = {}  # maps string content to label

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
        # Emit string literals in .rodata
        if self.strings:
            self.emit("")
            self.emit("    .section .rodata")
            for content, label in self.strings:
                self.emit(f"{label}:")
                # Emit each byte as .byte
                for ch in content:
                    self.emit(f"    .byte {ord(ch)}")
                self.emit("    .byte 0")  # null terminator
        return "\n".join(self.out) + "\n"

    def gen_func(self, func):
        if len(func) == 5:
            _, name, params, body, _ret_struct = func
        else:
            _, name, params, body = func
        if len(params) > 6:
            raise CompileError(f"{name}: more than 6 parameters not supported")
        locals_, array_sizes = _collect_locals(params, body, self.structs)
        self.array_sizes = array_sizes
        # Populate var_types from params and body before frame calculation
        self.var_types = {}
        for p in params:
            if isinstance(p, tuple) and p[0] == "struct":
                self.var_types[p[2]] = f"struct:{p[1]}"
            elif isinstance(p, tuple) and p[0] == "*":
                self.var_types[p[1]] = "int*"
        self._collect_var_types(body)
        # Compute stack offsets: arrays and structs get extra space
        self.off = {}
        offset = 0
        for nm in locals_:
            if nm in array_sizes and array_sizes[nm] > 0:
                size = array_sizes[nm]
                stype = self.var_types.get(nm, "")
                if stype.startswith("struct:") and stype.endswith("[]"):
                    struct_name = stype.split(":")[1].split("[")[0]
                    if struct_name in self.structs:
                        size_slots = self._struct_size(struct_name)
                        offset -= size * size_slots * 8
                    else:
                        offset -= size * 8
                else:
                    offset -= size * 8
                self.off[nm] = offset  # base of array (lowest address)
            else:
                # Check if this is a struct variable
                stype = self.var_types.get(nm, "")
                if stype.startswith("struct:") and not stype.endswith("*") and not stype.endswith("[]"):
                    struct_name = stype.split(":")[-1].split("*")[0].split("[")[0]
                    if struct_name in self.structs:
                        size_slots = self._struct_size(struct_name)
                        offset -= size_slots * 8
                    else:
                        offset -= 8
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
            if isinstance(p, tuple) and p[0] == "struct":
                pname = p[2]
                self.var_types[pname] = f"struct:{p[1]}"
                struct_name = p[1]
                if struct_name in self.structs:
                    total_slots = self._struct_size(struct_name)
                    for j in range(total_slots):
                        self.emit(f"    mov {j*8}({ARG_REGS[i]}), %rax")
                        self.emit(f"    mov %rax, {self.off[pname] + j*8}(%rbp)")
                else:
                    self.emit(f"    mov ({ARG_REGS[i]}), %rax")
                    self.emit(f"    mov %rax, {self.off[pname]}(%rbp)")
            elif isinstance(p, tuple) and p[0] == "*":
                pname = p[1]
                self.var_types[pname] = "int*"
                self.emit(f"    mov {ARG_REGS[i]}, {self.off[pname]}(%rbp)")
            else:
                pname = p
                self.emit(f"    mov {ARG_REGS[i]}, {self.off[pname]}(%rbp)")
        self.gen_stmt(body)
        self.emit("    mov $0, %rax")        # default return value on fall-through
        self.emit(f"{self.epilogue}:")
        self.emit("    leave")
        self.emit("    ret")

    def _collect_var_types(self, body):
        """Walk the AST to populate var_types for struct variables."""
        def walk(n):
            if not isinstance(n, tuple):
                return
            tag = n[0]
            if tag == "struct_var":
                self.var_types[n[2]] = f"struct:{n[1]}"
            elif tag == "structptrdecl":
                self.var_types[n[2]] = f"struct:{n[1]}*"
            elif tag == "structarraydecl":
                self.var_types[n[2]] = f"struct:{n[1]}[]"
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
            # ('struct_var', type_name, var_name, init_expr_or_None)
            self.var_types[n[2]] = f"struct:{n[1]}"
            if len(n) > 3 and n[3] is not None:
                self.gen_expr(n[3])
                # Check if the init value is a struct (pointer return from function)
                init = n[3]
                if isinstance(init, tuple) and init[0] == "call":
                    # Function returns a pointer to struct; copy the data
                    struct_name = n[1]
                    if struct_name in self.structs:
                        members = self.structs[struct_name]
                        self.emit("    mov %rax, %rcx")  # rcx = pointer to returned struct
                        for j in range(len(members)):
                            self.emit(f"    mov {j*8}(%rcx), %rax")
                            self.emit(f"    mov %rax, {self.off[n[2]] + j*8}(%rbp)")
                    else:
                        self.emit(f"    mov (%rax), %rax")
                        self.emit(f"    mov %rax, {self.off[n[2]]}(%rbp)")
                else:
                    self.emit(f"    mov %rax, {self.off[n[2]]}(%rbp)")
        elif tag == "structptrdecl":
            # ('structptrdecl', type_name, var_name, init_expr)
            self.var_types[n[2]] = f"struct:{n[1]}*"
            if n[3] is not None:
                self.gen_expr(n[3])
                self.emit(f"    mov %rax, {self.off[n[2]]}(%rbp)")
        elif tag == "structarraydecl":
            # ('structarraydecl', type_name, var_name, size_expr)
            self.var_types[n[2]] = f"struct:{n[1]}[]"
            pass  # space allocated in frame
        elif tag == "exprstmt":
            self.gen_expr(n[1])
        elif tag == "ret":
            if isinstance(n[1], tuple) and n[1][0] == "var":
                stype = self.var_types.get(n[1][1], "")
                if stype.startswith("struct:") and not stype.endswith("*") and not stype.endswith("[]"):
                    self.emit(f"    lea {self._slot(n[1][1])}, %rax")
                else:
                    self.gen_expr(n[1])
            else:
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
        elif tag == "strlit":
            content = n[1]
            if content not in self.string_map:
                label = self.label("str")
                self.strings.append((content, label))
                self.string_map[content] = label
            label = self.string_map[content]
            self.emit(f"    lea {label}(%rip), %rax")
        elif tag == "var":
            name = n[1]
            if name in self.enum_values:
                self.emit(f"    mov ${self.enum_values[name]}, %rax")
            else:
                self.emit(f"    mov {self._slot(name)}, %rax")
        elif tag == "un":
            op = n[1]
            if op == "&":
                # address-of: load effective address of lvalue
                inner = n[2]
                if isinstance(inner, tuple) and inner[0] == "var":
                    self.emit(f"    lea {self._slot(inner[1])}, %rax")
                elif isinstance(inner, tuple) and inner[0] == "subscript":
                    self._gen_subscript_addr(inner[1], inner[2])
                elif isinstance(inner, tuple) and inner[0] == "member":
                    self._gen_member_addr(inner[1], inner[2])
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
                if isinstance(a, tuple) and a[0] == "var":
                    stype = self.var_types.get(a[1], "")
                    if stype.startswith("struct:") and not stype.endswith("*") and not stype.endswith("[]"):
                        self.emit(f"    lea {self._slot(a[1])}, %rax")
                    else:
                        self.gen_expr(a)
                else:
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

    def _struct_member_offset(self, struct_name, member_name):
        """Compute byte offset of a member within a struct."""
        members = self.structs.get(struct_name, [])
        offset = 0
        for m in members:
            mname = m[0] if isinstance(m, tuple) else m
            mtype = m[1] if isinstance(m, tuple) else "int"
            if mname == member_name:
                return offset
            if mtype.startswith("struct:"):
                inner_struct = mtype[7:]
                offset += self._struct_size(inner_struct) * 8
            elif mtype.endswith("[]"):
                offset += 8
            else:
                offset += 8
        return offset

    def _gen_member_addr(self, obj, member):
        """Generate code to load address of struct member into %rax."""
        # Handle dereference (struct pointer -> member)
        if isinstance(obj, tuple) and obj[0] == "un" and obj[1] == "*":
            # p->x: gen_expr loads pointer value (address) into %rax
            self.gen_expr(obj[2])
            # Get struct type from the pointer type
            ptr_type = self._resolve_type(obj[2])
            if ptr_type.endswith("*"):
                struct_name = ptr_type[:-1].split(":")[-1]
                offset = self._struct_member_offset(struct_name, member)
                if offset:
                    self.emit(f"    add ${offset}, %rax")
            return
        # Handle subscript results (array[i].member)
        if isinstance(obj, tuple) and obj[0] == "subscript":
            self._gen_subscript_addr(obj[1], obj[2])
            # Find member offset
            arr_type = self._resolve_type(obj[1])
            struct_name = arr_type.split(":")[-1].split("[")[0]
            offset = self._struct_member_offset(struct_name, member)
            if offset:
                self.emit(f"    add ${offset}, %rax")
            return
        # Handle member results (obj.member.member)
        if isinstance(obj, tuple) and obj[0] == "member":
            self._gen_member_addr(obj[1], obj[2])
            # Resolve the type of the intermediate member (obj[1].obj[2])
            parent_struct = self._resolve_struct_name(obj[1])
            if parent_struct:
                mtype = self._get_member_type(parent_struct, obj[2])
                if mtype and mtype.startswith("struct:"):
                    inner_struct = mtype[7:]
                    offset = self._struct_member_offset(inner_struct, member)
                    if offset:
                        self.emit(f"    add ${offset}, %rax")
            return
        # Handle variable access
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
        struct_name = stype.split(":")[-1].split("*")[0].split("[")[0]
        if struct_name not in self.structs:
            raise CompileError(f"unknown struct type '{struct_name}'")
        offset = self._struct_member_offset(struct_name, member)
        self.emit(f"    lea {slot}, %rax")
        if offset:
            self.emit(f"    add ${offset}, %rax")

    def _resolve_type(self, expr):
        """Resolve the type of an expression (for struct member access)."""
        if isinstance(expr, tuple) and expr[0] == "var":
            return self.var_types.get(expr[1], "int")
        elif isinstance(expr, str):
            return self.var_types.get(expr, "int")
        elif isinstance(expr, tuple) and expr[0] == "un" and expr[1] == "*":
            inner = self._resolve_type(expr[2])
            if inner.endswith("*"):
                return inner[:-1]
            return "int"
        elif isinstance(expr, tuple) and expr[0] == "member":
            obj_type = self._resolve_type(expr[1])
            if obj_type.startswith("struct:"):
                base = obj_type.split("*")[0].split("[")[0]
                sname = base[7:]
                mtype = self._get_member_type(sname, expr[2])
                if mtype:
                    return mtype
            return "int"
        elif isinstance(expr, tuple) and expr[0] == "subscript":
            arr_type = self._resolve_type(expr[1])
            return arr_type.split("[")[0]
        return "int"

    def _resolve_struct_name(self, expr):
        """Resolve the struct name of an expression."""
        if isinstance(expr, tuple) and expr[0] == "var":
            name = expr[1]
        elif isinstance(expr, str):
            name = expr
        elif isinstance(expr, tuple) and expr[0] == "un" and expr[1] == "*":
            inner_type = self._resolve_type(expr[2])
            if inner_type.endswith("*"):
                base = inner_type[:-1]
                if base.startswith("struct:"):
                    return base[7:]
            return None
        elif isinstance(expr, tuple) and expr[0] == "member":
            obj_type = self._resolve_type(expr[1])
            if obj_type.startswith("struct:"):
                base = obj_type.split("*")[0].split("[")[0]
                sname = base[7:]
                mtype = self._get_member_type(sname, expr[2])
                if mtype and mtype.startswith("struct:"):
                    return mtype[7:]
            return None
        elif isinstance(expr, tuple) and expr[0] == "subscript":
            arr_type = self._resolve_type(expr[1])
            base = arr_type.split("[")[0]
            if base.startswith("struct:"):
                return base[7:]
            return None
        else:
            return None
        stype = self.var_types.get(name, "")
        if stype.startswith("struct:"):
            return stype.split(":")[1].split("*")[0].split("[")[0]
        return None

    def _get_member_type(self, struct_name, member_name):
        """Get the type of a member within a struct."""
        members = self.structs.get(struct_name, [])
        for m in members:
            mname = m[0] if isinstance(m, tuple) else m
            mtype = m[1] if isinstance(m, tuple) else "int"
            if mname == member_name:
                return mtype
        return None

    def _struct_size(self, struct_name):
        """Compute total size of a struct in 8-byte slots, accounting for nested structs."""
        members = self.structs.get(struct_name, [])
        total = 0
        for m in members:
            mtype = m[1] if isinstance(m, tuple) else "int"
            if mtype.startswith("struct:"):
                inner = mtype[7:]
                total += self._struct_size(inner)
            else:
                total += 1
        return total

    def _gen_subscript_addr(self, array_expr, index_expr):
        """Generate code to load address of array element into %rax.
        Computes: base_addr + index * element_size."""
        # Handle string literal subscript
        if isinstance(array_expr, tuple) and array_expr[0] == "strlit":
            content = array_expr[1]
            if content not in self.string_map:
                label = self.label("str")
                self.strings.append((content, label))
                self.string_map[content] = label
            label = self.string_map[content]
            self.gen_expr(index_expr)
            self.emit(f"    lea {label}(%rip), %rcx")
            self.emit("    add %rcx, %rax")
            return
        if isinstance(array_expr, tuple) and array_expr[0] == "var":
            arr_name = array_expr[1]
        elif isinstance(array_expr, str):
            arr_name = array_expr
        else:
            raise CompileError("array subscript on non-variable")
        slot = self._slot(arr_name)
        self.gen_expr(index_expr)
        stype = self.var_types.get(arr_name, "")
        if stype.startswith("struct:") and stype.endswith("[]"):
            struct_name = stype.split(":")[1].split("[")[0]
            if struct_name in self.structs:
                elem_size = self._struct_size(struct_name) * 8
            else:
                elem_size = 8
        else:
            elem_size = 8
        if elem_size == 8:
            self.emit("    shl $3, %rax")
        else:
            self.emit(f"    imul ${elem_size}, %rax")
        self.emit(f"    lea {slot}, %rcx")
        self.emit("    add %rcx, %rax")


def generate(ast, enum_values=None, structs=None):
    """AST -> x86-64 assembly text."""
    return Gen(enum_values, structs).gen_program(ast)
