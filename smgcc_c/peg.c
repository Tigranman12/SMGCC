/* peg.c — META II / PEG pattern-matching engine (C port).

   Matches input against grammar nodes with PEG-style ordered choice
   and backtracking.
*/

#include "peg.h"

/* ---- grammar builder ---- */

void grammar_init(Grammar *g) {
    g->node_count = 0;
    g->rule_count = 0;
}

int grammar_add_rule(Grammar *g, int start_node) {
    int idx = g->rule_count;
    g->rule_starts[idx] = start_node;
    g->rule_count++;
    return idx;
}

int node_lit(Grammar *g, const char *text, int len) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_LIT;
    n->u.lit.text = text;
    n->u.lit.len = len;
    g->node_count++;
    return idx;
}

int node_range(Grammar *g, char lo, char hi) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_RANGE;
    n->u.range.lo = lo;
    n->u.range.hi = hi;
    g->node_count++;
    return idx;
}

int node_seq(Grammar *g, int *children, int count) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_SEQ;
    n->u.seq.children = children;
    n->u.seq.count = count;
    g->node_count++;
    return idx;
}

int node_choice(Grammar *g, int *children, int count) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_CHOICE;
    n->u.seq.children = children;
    n->u.seq.count = count;
    g->node_count++;
    return idx;
}

int node_star(Grammar *g, int child) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_STAR;
    n->u.wrap.child = child;
    g->node_count++;
    return idx;
}

int node_plus(Grammar *g, int child) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_PLUS;
    n->u.wrap.child = child;
    g->node_count++;
    return idx;
}

int node_opt(Grammar *g, int child) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_OPT;
    n->u.wrap.child = child;
    g->node_count++;
    return idx;
}

int node_not(Grammar *g, int child) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_NOT;
    n->u.wrap.child = child;
    g->node_count++;
    return idx;
}

int node_and(Grammar *g, int child) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_AND;
    n->u.wrap.child = child;
    g->node_count++;
    return idx;
}

int node_ref(Grammar *g, int rule_index) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_REF;
    n->u.ref.index = rule_index;
    g->node_count++;
    return idx;
}

int node_act(Grammar *g, int rule_index) {
    int idx = g->node_count;
    Node *n = &g->nodes[idx];
    n->tag = N_ACT;
    n->u.act.rule_index = rule_index;
    g->node_count++;
    return idx;
}

/* ---- matcher ---- */

static char input_at(Input *in, int pos) {
    if (pos >= 0 && pos < in->len) return in->buf[pos];
    return '\0';
}

static void update_max(ParseState *st) {
    if (st->pos > st->max_pos) st->max_pos = st->pos;
}

static MatchResult fail_result(void) {
    MatchResult r;
    r.ok = 0;
    r.consumed = 0;
    return r;
}

static MatchResult ok_result(int consumed) {
    MatchResult r;
    r.ok = 1;
    r.consumed = consumed;
    return r;
}

MatchResult match(Grammar *g, ParseState *st, int node_index) {
    Node *n = &g->nodes[node_index];
    int saved;
    int total;
    int i;
    MatchResult sub;
    char c;

    if (st->depth > MAX_STACK) return fail_result();
    st->depth++;

    switch (n->tag) {

    case N_LIT: {
        int len = n->u.lit.len;
        if (st->pos + len > st->input.len) { st->depth--; return fail_result(); }
        for (i = 0; i < len; i++) {
            if (st->input.buf[st->pos + i] != n->u.lit.text[i]) {
                update_max(st);
                st->depth--;
                return fail_result();
            }
        }
        st->pos += len;
        st->depth--;
        return ok_result(len);
    }

    case N_RANGE: {
        if (st->pos >= st->input.len) { st->depth--; return fail_result(); }
        c = input_at(&st->input, st->pos);
        if (c >= n->u.range.lo && c <= n->u.range.hi) {
            st->pos++;
            st->depth--;
            return ok_result(1);
        }
        update_max(st);
        st->depth--;
        return fail_result();
    }

    case N_SEQ: {
        saved = st->pos;
        total = 0;
        for (i = 0; i < n->u.seq.count; i++) {
            sub = match(g, st, n->u.seq.children[i]);
            if (!sub.ok) {
                st->pos = saved;
                st->depth--;
                return fail_result();
            }
            total += sub.consumed;
        }
        st->depth--;
        return ok_result(total);
    }

    case N_CHOICE: {
        saved = st->pos;
        for (i = 0; i < n->u.seq.count; i++) {
            sub = match(g, st, n->u.seq.children[i]);
            if (sub.ok) {
                st->depth--;
                return sub;
            }
            st->pos = saved;
        }
        st->depth--;
        return fail_result();
    }

    case N_STAR: {
        total = 0;
        for (;;) {
            saved = st->pos;
            sub = match(g, st, n->u.wrap.child);
            if (!sub.ok) {
                st->pos = saved;
                break;
            }
            total += sub.consumed;
            if (sub.consumed == 0) break;
        }
        st->depth--;
        return ok_result(total);
    }

    case N_PLUS: {
        sub = match(g, st, n->u.wrap.child);
        if (!sub.ok) { st->depth--; return fail_result(); }
        total = sub.consumed;
        for (;;) {
            saved = st->pos;
            sub = match(g, st, n->u.wrap.child);
            if (!sub.ok || sub.consumed == 0) {
                st->pos = saved;
                break;
            }
            total += sub.consumed;
        }
        st->depth--;
        return ok_result(total);
    }

    case N_OPT: {
        saved = st->pos;
        sub = match(g, st, n->u.wrap.child);
        if (!sub.ok) {
            st->pos = saved;
            st->depth--;
            return ok_result(0);
        }
        st->depth--;
        return sub;
    }

    case N_NOT: {
        saved = st->pos;
        sub = match(g, st, n->u.wrap.child);
        st->pos = saved;
        st->depth--;
        if (sub.ok) return fail_result();
        return ok_result(0);
    }

    case N_AND: {
        saved = st->pos;
        sub = match(g, st, n->u.wrap.child);
        st->pos = saved;
        st->depth--;
        if (sub.ok) return ok_result(0);
        return fail_result();
    }

    case N_REF: {
        sub = match(g, st, g->rule_starts[n->u.ref.index]);
        st->depth--;
        return sub;
    }

    case N_ACT: {
        /* Action node: just match the rule, semantics handled externally */
        sub = match(g, st, g->rule_starts[n->u.act.rule_index]);
        st->depth--;
        return sub;
    }

    }

    st->depth--;
    return fail_result();
}

MatchResult parse(Grammar *g, const char *input, int len) {
    ParseState st;
    st.input.buf = input;
    st.input.len = len;
    st.pos = 0;
    st.max_pos = 0;
    st.depth = 0;
    return match(g, &st, g->rule_starts[0]);
}
