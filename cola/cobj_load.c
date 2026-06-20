/* cobj_load.c — REFERENCE loader for SMGCC-compiled .cobj modules.
 *
 * This is a PROPOSED addition for LW_OS milestone M7. It is NOT part of LW_OS
 * (that tree was analyzed read-only) and is not built here — it documents
 * exactly how the OS would load a .cobj produced by `colac.py` and run it on the
 * existing COLA VM. Drop it into phase8-cola-metal/ and call cobj_load_run().
 *
 * .cobj text format (see cola/cobj.py):
 *     COBJ1
 *     consts <N>
 *     int <i> <value>
 *     str <i> <text-to-eol>
 *     sym <i> <name>
 *     code <M>
 *     <i> <OPNAME> <arg>
 */
#include "cola/cola.h"
#include "cola/cola_vm.h"
#include "cola/klibc.h"

/* opcode-name table — index == ColaOpCode value (matches cola_vm.h order). */
static const char *OPNAMES[] = {
    "NOP","HALT","PUSH_INT","PUSH_SYM","PUSH_NIL","PUSH_TRUE","PUSH_FALSE",
    "PUSH_CONST","POP","DUP","PUSH_LOCAL","STORE_LOCAL","PUSH_GLOBAL",
    "STORE_GLOBAL","SEND","MAKE_OBJ","GET_SLOT","SET_SLOT","MAKE_CLOSURE",
    "CALL","RETURN","JUMP","BRANCH_FALSE","BRANCH_TRUE","ADD","SUB","MUL","DIV",
    "MOD","EQ","LT","GT","NOT","PRINT","NEWLINE","CONCAT",
};
#define N_OPNAMES (int)(sizeof(OPNAMES)/sizeof(OPNAMES[0]))

static int op_from_name(const char *s) {
    for (int i = 0; i < N_OPNAMES; i++)
        if (k_strcmp(OPNAMES[i], s) == 0) return i;
    return -1;
}

/* tiny line/token scanner over an in-memory buffer */
static int next_line(const char *src, int *pos, char *buf, int cap) {
    int n = 0;
    if (src[*pos] == 0) return 0;
    while (src[*pos] && src[*pos] != '\n') {
        if (n < cap - 1) buf[n++] = src[*pos];
        (*pos)++;
    }
    if (src[*pos] == '\n') (*pos)++;
    buf[n] = 0;
    return 1;
}

static int parse_int(const char *s, int *out_end) {
    int i = 0, sign = 1, v = 0;
    while (s[i] == ' ') i++;
    if (s[i] == '-') { sign = -1; i++; }
    while (s[i] >= '0' && s[i] <= '9') { v = v * 10 + (s[i] - '0'); i++; }
    if (out_end) *out_end = i;
    return v * sign;
}

/* Load a .cobj text buffer into prog. Returns 0 on success, -1 on error. */
int cobj_load(Cola *c, ColaProgram *prog, const char *src) {
    char line[320];
    int pos = 0, used;

    if (!next_line(src, &pos, line, sizeof line) || k_strcmp(line, "COBJ1") != 0)
        return -1;

    /* consts <N> */
    if (!next_line(src, &pos, line, sizeof line)) return -1;
    int n_consts = parse_int(line + 7, 0);          /* skip "consts " */
    for (int k = 0; k < n_consts; k++) {
        if (!next_line(src, &pos, line, sizeof line)) return -1;
        if (line[0] == 'i') {                         /* "int <i> <value>" */
            const char *p = line + 4;
            parse_int(p, &used); p += used;           /* index (ignored) */
            int val = parse_int(p, 0);
            cola_prog_add_const(prog, MAKE_INT(val));
        } else if (line[0] == 's' && line[1] == 'y') { /* "sym <i> <name>" */
            const char *p = line + 4;
            parse_int(p, &used); p += used;
            while (*p == ' ') p++;
            cola_prog_add_const(prog, cola_intern(c, p));
        } else if (line[0] == 's' && line[1] == 't') { /* "str <i> <text>" */
            const char *p = line + 4;
            parse_int(p, &used); p += used;
            while (*p == ' ') p++;
            cola_prog_add_const(prog, cola_alloc_string(c, p, k_strlen(p)));
        } else {
            return -1;
        }
    }

    /* code <M> */
    if (!next_line(src, &pos, line, sizeof line)) return -1;
    int n_code = parse_int(line + 5, 0);              /* skip "code " */
    for (int k = 0; k < n_code; k++) {
        if (!next_line(src, &pos, line, sizeof line)) return -1;
        const char *p = line;
        parse_int(p, &used); p += used;               /* instr index (ignored) */
        while (*p == ' ') p++;
        char name[24]; int n = 0;
        while (*p && *p != ' ' && n < 23) name[n++] = *p++;
        name[n] = 0;
        int arg = parse_int(p, 0);
        int op = op_from_name(name);
        if (op < 0) return -1;
        cola_prog_emit(prog, (ColaOpCode)op, arg);
    }
    return 0;
}

/* Convenience: load + run a .cobj, printing through the kernel's putchar. */
int cobj_load_run(Cola *c, const char *src) {
    ColaProgram prog;
    cola_prog_init(&prog);
    if (cobj_load(c, &prog, src) != 0) {
        k_puts("cobj: bad module\n");
        return -1;
    }
    ColaVM vm;
    cola_vm_init(&vm, c, &prog);
    return cola_vm_run(&vm);
}
