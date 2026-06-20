"""COLA-VM opcode numbers — MUST match the enum order in
LW_OS/phase8-cola-metal/cola/cola_vm.h exactly."""

OPCODES = {
    "NOP": 0, "HALT": 1,
    "PUSH_INT": 2, "PUSH_SYM": 3, "PUSH_NIL": 4, "PUSH_TRUE": 5, "PUSH_FALSE": 6,
    "PUSH_CONST": 7,
    "POP": 8, "DUP": 9,
    "PUSH_LOCAL": 10, "STORE_LOCAL": 11,
    "PUSH_GLOBAL": 12, "STORE_GLOBAL": 13,
    "SEND": 14, "MAKE_OBJ": 15, "GET_SLOT": 16, "SET_SLOT": 17,
    "MAKE_CLOSURE": 18, "CALL": 19, "RETURN": 20,
    "JUMP": 21, "BRANCH_FALSE": 22, "BRANCH_TRUE": 23,
    "ADD": 24, "SUB": 25, "MUL": 26, "DIV": 27, "MOD": 28,
    "EQ": 29, "LT": 30, "GT": 31, "NOT": 32, "PRINT": 33, "NEWLINE": 34,
    "CONCAT": 35,
}

NAMES = {v: k for k, v in OPCODES.items()}
