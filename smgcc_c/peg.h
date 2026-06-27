/* peg.h — META II / PEG pattern-matching engine (C port).

   Matches input against grammar nodes with PEG-style ordered choice
   and backtracking. Rules may carry output actions that build an AST.

   This is the seed for self-hosting: the same engine that the Python
   version uses, rewritten in the C subset SMGCC already compiles.
*/

#ifndef PEG_H
#define PEG_H

#define MAX_RULES 256
#define MAX_STACK 1024
#define MAX_NODES 2048

/* ---- input string ---- */
typedef struct {
    const char *buf;
    int len;
} Input;

/* ---- node tags ---- */
enum NodeTag {
    N_LIT,      /* literal string */
    N_RANGE,    /* character range [a-z] */
    N_SEQ,      /* sequence of nodes */
    N_CHOICE,   /* ordered choice / */
    N_STAR,     /* zero or more */
    N_PLUS,     /* one or more */
    N_OPT,      /* optional */
    N_NOT,      /* negative lookahead */
    N_AND,      /* positive lookahead */
    N_REF,      /* rule reference by index */
    N_ACT,      /* output action (semantic) */
};

/* ---- grammar node ---- */
typedef struct Node {
    enum NodeTag tag;
    union {
        /* N_LIT */
        struct { const char *text; int len; } lit;
        /* N_RANGE */
        struct { char lo; char hi; } range;
        /* N_SEQ, N_CHOICE */
        struct { int *children; int count; } seq;
        /* N_STAR, N_PLUS, N_OPT, N_NOT, N_AND */
        struct { int child; } wrap;
        /* N_REF */
        struct { int index; } ref;
        /* N_ACT */
        struct { int rule_index; } act;
    } u;
} Node;

/* ---- parse state ---- */
typedef struct {
    Input input;
    int pos;
    int max_pos;
    int depth;
} ParseState;

/* ---- match result ---- */
typedef struct {
    int ok;
    int consumed;
} MatchResult;

/* ---- grammar (collection of nodes + named rules) ---- */
typedef struct {
    Node nodes[MAX_NODES];
    int node_count;
    int rule_starts[MAX_RULES];  /* index into nodes[] for each rule */
    int rule_count;
} Grammar;

/* ---- API ---- */
void grammar_init(Grammar *g);
int  grammar_add_rule(Grammar *g, int start_node);
MatchResult match(Grammar *g, ParseState *st, int node_index);
MatchResult parse(Grammar *g, const char *input, int len);

/* ---- node builders ---- */
int node_lit(Grammar *g, const char *text, int len);
int node_range(Grammar *g, char lo, char hi);
int node_seq(Grammar *g, int *children, int count);
int node_choice(Grammar *g, int *children, int count);
int node_star(Grammar *g, int child);
int node_plus(Grammar *g, int child);
int node_opt(Grammar *g, int child);
int node_not(Grammar *g, int child);
int node_and(Grammar *g, int child);
int node_ref(Grammar *g, int rule_index);
int node_act(Grammar *g, int rule_index);

#endif /* PEG_H */
