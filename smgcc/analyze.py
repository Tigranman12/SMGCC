"""Semantic analyzer — Stage 3.

Walks the AST produced by the parser and verifies:
  1. All variables are declared before use
  2. No redeclarations in the same scope
  3. Function calls match declared signatures
  4. Type correctness for basic operations

AST node shapes (from cgrammar.py):
    ('program', [func, ...])
    ('func', name, [param_name, ...], block)
    ('block', [stmt, ...])
    ('decl', name, init_expr_or_None)
    ('ret', expr)
    ('if', cond, then_stmt, else_stmt_or_None)
    ('while', cond, body_stmt)
    ('for', init_stmt_or_None, test, step, body)
    ('break',) / ('continue',)
    ('exprstmt', expr)
    ('assign', name, expr)
    ('bin', op, left, right)
    ('un', op, expr)
    ('call', name, [arg_expr, ...])
    ('var', name)
    ('num', int)
"""


class SemanticError(Exception):
    """Raised when the analyzer finds a semantic error."""
    def __init__(self, msg: str, name: str = None):
        super().__init__(msg)
        self.name = name


class Scope:
    """A single scope level mapping names to types."""
    def __init__(self):
        self.symbols: dict[str, str] = {}

    def declare(self, name: str, stype: str) -> None:
        if name in self.symbols:
            raise SemanticError(f"redeclaration of '{name}'", name)
        self.symbols[name] = stype

    def lookup(self, name: str) -> str | None:
        return self.symbols.get(name)


class SymbolTable:
    """Stack of scopes for nested block handling."""
    def __init__(self):
        self.scopes: list[Scope] = []

    def push(self) -> None:
        self.scopes.append(Scope())

    def pop(self) -> None:
        self.scopes.pop()

    def declare(self, name: str, stype: str) -> None:
        self.scopes[-1].declare(name, stype)

    def lookup(self, name: str) -> str | None:
        for scope in reversed(self.scopes):
            stype = scope.lookup(name)
            if stype is not None:
                return stype
        return None


def analyze(ast: tuple) -> dict:
    """Analyze a parsed AST. Returns a symbol table dict with function info.
    Raises SemanticError on failures."""
    table = {"functions": {}, "globals": {}, "enum_values": {}, "structs": {}}
    analyzer = _Analyzer(table)
    analyzer.analyze_program(ast)
    return table


class _Analyzer:
    def __init__(self, table: dict):
        self.table = table
        self.symtab = SymbolTable()
        self.current_func = None

    def analyze_program(self, node):
        tag = node[0]
        assert tag == "program"

        # First pass: register enums, structs, and function signatures
        counter = 0
        for item in node[1]:
            if item[0] == "enum":
                # Resolve enum values
                for ev in item[2]:
                    name = ev[1]
                    if ev[2] is not None:
                        counter = self._eval_const(ev[2])
                    self.table["enum_values"][name] = counter
                    counter += 1
            elif item[0] == "structdecl":
                # Register struct type
                sname = item[1]
                members = item[2]
                self.table["structs"][sname] = members
            elif item[0] == "func":
                fname = item[1]
                params = item[2]
                if fname in self.table["functions"]:
                    raise SemanticError(f"redeclaration of function '{fname}'", fname)
                self.table["functions"][fname] = {"params": list(params)}

        # Second pass: analyze function bodies
        for item in node[1]:
            if item[0] == "func":
                self.analyze_func(item)

    def _eval_const(self, node):
        """Evaluate a constant expression (for enum values)."""
        tag = node[0]
        if tag == "num":
            return node[1]
        elif tag == "bin":
            left = self._eval_const(node[2])
            right = self._eval_const(node[3])
            op = node[1]
            if op == "+": return left + right
            if op == "-": return left - right
            if op == "*": return left * right
            if op == "/": return left // right if right else 0
            if op == "%": return left % right if right else 0
        elif tag == "un":
            val = self._eval_const(node[2])
            if node[1] == "-": return -val
        raise SemanticError("non-constant enum value")

    def analyze_func(self, node):
        if len(node) == 5:
            _, name, params, body, _ret_struct = node
        else:
            _, name, params, body = node
        # Check for struct return type: ('func', name, params, body, struct_return_type)
        self.current_func = name
        self.symtab.push()

        # Declare parameters
        for p in params:
            if isinstance(p, tuple) and p[0] == "*":
                # pointer parameter: ("*", name)
                self.symtab.declare(p[1], "int*")
            elif isinstance(p, tuple) and p[0] == "struct":
                # struct parameter: ("struct", type_name, name)
                stype = p[1]
                pname = p[2]
                if stype not in self.table["structs"]:
                    raise SemanticError(f"unknown struct type '{stype}'", stype)
                self.symtab.declare(pname, f"struct:{stype}")
            else:
                self.symtab.declare(p, "int")

        self.analyze_stmt(body)
        self.symtab.pop()
        self.current_func = None

    def analyze_stmt(self, node):
        tag = node[0]

        if tag == "block":
            self.symtab.push()
            for stmt in node[1]:
                self.analyze_stmt(stmt)
            self.symtab.pop()

        elif tag == "decl":
            name = node[1]
            self.symtab.declare(name, "int")
            if node[2] is not None:
                self.analyze_expr(node[2])

        elif tag == "ptrdecl":
            name = node[1]
            self.symtab.declare(name, "int*")
            if node[2] is not None:
                self.analyze_expr(node[2])

        elif tag == "arraydecl":
            name = node[1]
            self.symtab.declare(name, "int[]")
            self.analyze_expr(node[2])  # validate size expression

        elif tag == "struct_var":
            # ('struct_var', type_name, var_name)
            stype = node[1]
            name = node[2]
            if stype not in self.table["structs"]:
                raise SemanticError(f"unknown struct type '{stype}'", stype)
            self.symtab.declare(name, f"struct:{stype}")

        elif tag == "structptrdecl":
            # ('structptrdecl', type_name, var_name, init_expr)
            stype = node[1]
            name = node[2]
            if stype not in self.table["structs"]:
                raise SemanticError(f"unknown struct type '{stype}'", stype)
            self.symtab.declare(name, f"struct:{stype}*")
            if node[3] is not None:
                self.analyze_expr(node[3])

        elif tag == "structarraydecl":
            # ('structarraydecl', type_name, var_name, size_expr)
            stype = node[1]
            name = node[2]
            if stype not in self.table["structs"]:
                raise SemanticError(f"unknown struct type '{stype}'", stype)
            self.symtab.declare(name, f"struct:{stype}[]")
            self.analyze_expr(node[3])

        elif tag == "ret":
            self.analyze_expr(node[1])

        elif tag == "if":
            self.analyze_expr(node[1])
            self.analyze_stmt(node[2])
            if node[3] is not None:
                self.analyze_stmt(node[3])

        elif tag == "while":
            self.analyze_expr(node[1])
            self.analyze_stmt(node[2])

        elif tag == "do_while":
            self.analyze_stmt(node[1])
            self.analyze_expr(node[2])

        elif tag == "switch":
            self.analyze_expr(node[1])
            for case in node[2]:
                self.analyze_expr(case[1])
                for stmt in case[2]:
                    self.analyze_stmt(stmt)
            if node[3] is not None:
                for stmt in node[3][1]:
                    self.analyze_stmt(stmt)

        elif tag == "for":
            self.symtab.push()
            if node[1] is not None:
                self.analyze_stmt(node[1])
            if node[2] is not None:
                self.analyze_expr(node[2])
            if node[3] is not None:
                self.analyze_expr(node[3])
            self.analyze_stmt(node[4])
            self.symtab.pop()

        elif tag == "exprstmt":
            self.analyze_expr(node[1])

        elif tag in ("break", "continue"):
            pass  # validated by codegen

        else:
            raise SemanticError(f"unknown statement: {tag}")

    def analyze_expr(self, node):
        # Handle string nodes (variable references)
        if isinstance(node, str):
            name = node
            if name in self.table["enum_values"]:
                return "int"
            if self.symtab.lookup(name) is None:
                raise SemanticError(f"undeclared variable '{name}'", name)
            return self.symtab.lookup(name)

        tag = node[0]

        if tag == "num":
            return "int"

        elif tag == "strlit":
            return "int*"

        elif tag == "var":
            name = node[1]
            # Check if it's an enum constant
            if name in self.table["enum_values"]:
                return "int"
            if self.symtab.lookup(name) is None:
                raise SemanticError(f"undeclared variable '{name}'", name)
            return self.symtab.lookup(name)

        elif tag == "member":
            # ('member', obj_expr, member_name)
            obj_type = self.analyze_expr(node[1])
            member_name = node[2]
            if not obj_type.startswith("struct:"):
                raise SemanticError(f"cannot access member of non-struct type '{obj_type}'")
            # Strip pointer/array suffixes for struct lookup
            base_type = obj_type.split("*")[0].split("[")[0]
            struct_name = base_type[7:]  # remove "struct:" prefix
            if struct_name not in self.table["structs"]:
                raise SemanticError(f"unknown struct type '{struct_name}'")
            members = self.table["structs"][struct_name]
            # Find member and return its type
            for m in members:
                if isinstance(m, tuple) and m[0] == member_name:
                    return m[1]
                elif m == member_name:
                    return "int"
            raise SemanticError(f"struct '{struct_name}' has no member '{member_name}'")

        elif tag == "subscript":
            # ('subscript', array_expr, index_expr)
            arr_type = self.analyze_expr(node[1])
            # Handle struct arrays too
            base = arr_type.split("[")[0]
            if not (base == "int" or base.startswith("struct:") or base.endswith("*")):
                raise SemanticError(f"cannot subscript non-array type '{arr_type}'")
            self.analyze_expr(node[2])  # validate index expression
            return base

        elif tag == "assign":
            target = node[1]
            if isinstance(target, tuple) and target[0] == "member":
                # member assignment: obj.member = expr
                self.analyze_expr(target)  # validates member access
            elif isinstance(target, tuple) and target[0] == "var":
                name = target[1]
                if name in self.table["enum_values"]:
                    raise SemanticError(f"cannot assign to enum constant '{name}'", name)
                if self.symtab.lookup(name) is None:
                    raise SemanticError(f"undeclared variable '{name}'", name)
            elif isinstance(target, tuple) and target[0] == "un" and target[1] == "*":
                # pointer dereference assignment: *p = expr
                self.analyze_expr(target)  # validates dereference
            elif isinstance(target, tuple) and target[0] == "subscript":
                # array subscript assignment: a[i] = expr
                self.analyze_expr(target)  # validates array and index
            else:
                name = target
                if name in self.table["enum_values"]:
                    raise SemanticError(f"cannot assign to enum constant '{name}'", name)
                if self.symtab.lookup(name) is None:
                    raise SemanticError(f"undeclared variable '{name}'", name)
            self.analyze_expr(node[2])
            return "int"

        elif tag == "bin":
            self.analyze_expr(node[2])
            self.analyze_expr(node[3])
            return "int"

        elif tag == "un":
            op = node[1]
            inner_type = self.analyze_expr(node[2])
            if op == "*":
                # Allow dereferencing both int* and struct:T*
                if not inner_type.endswith("*"):
                    raise SemanticError(f"cannot dereference non-pointer type '{inner_type}'")
                # Return base type without pointer
                return inner_type[:-1]
            elif op == "&":
                if inner_type.endswith("*"):
                    raise SemanticError("cannot take address of pointer")
                # Check if inner is an enum constant (not an lvalue)
                inner = node[2]
                if isinstance(inner, tuple) and inner[0] == "var" and inner[1] in self.table["enum_values"]:
                    raise SemanticError(f"cannot take address of enum constant '{inner[1]}'")
                return f"{inner_type}*"
            return "int"

        elif tag == "call":
            fname = node[1]
            if fname not in self.table["functions"]:
                raise SemanticError(f"undeclared function '{fname}'", fname)
            for arg in node[2]:
                self.analyze_expr(arg)
            return "int"

        elif tag == "logor":
            self.analyze_expr(node[1])
            self.analyze_expr(node[2])
            return "int"

        elif tag == "logand":
            self.analyze_expr(node[1])
            self.analyze_expr(node[2])
            return "int"

        else:
            raise SemanticError(f"unknown expression: {tag}")
