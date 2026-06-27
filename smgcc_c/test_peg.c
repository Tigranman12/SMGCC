/* test_peg.c — Tests for the C PEG engine.

   Compile with SMGCC:
     python3 cc.py smgcc_c/test_peg.c -o test_peg
     ./test_peg

   Or compile with gcc for development:
     gcc -o test_peg smgcc_c/peg.c smgcc_c/test_peg.c && ./test_peg
*/

#include <stdio.h>
#include <string.h>
#include "peg.h"

static int tests_run = 0;
static int tests_passed = 0;

static void check(const char *name, int cond) {
    tests_run++;
    if (cond) {
        tests_passed++;
    } else {
        printf("  FAIL: %s\n", name);
    }
}

/* ---- Test 1: literal matching ---- */
static void test_literal(void) {
    Grammar g;
    grammar_init(&g);

    int lit = node_lit(&g, "hello", 5);
    grammar_add_rule(&g, lit);

    MatchResult r;
    r = parse(&g, "hello", 5);
    check("literal match", r.ok && r.consumed == 5);

    r = parse(&g, "world", 5);
    check("literal mismatch", !r.ok);

    r = parse(&g, "hello!", 6);
    check("literal partial", r.ok && r.consumed == 5);
}

/* ---- Test 2: range matching ---- */
static void test_range(void) {
    Grammar g;
    grammar_init(&g);

    int digit = node_range(&g, '0', '9');
    grammar_add_rule(&g, digit);

    MatchResult r;
    r = parse(&g, "5", 1);
    check("range match digit", r.ok && r.consumed == 1);

    r = parse(&g, "a", 1);
    check("range mismatch", !r.ok);

    r = parse(&g, "0", 1);
    check("range match low", r.ok);

    r = parse(&g, "9", 1);
    check("range match high", r.ok);
}

/* ---- Test 3: sequence ---- */
static void test_sequence(void) {
    Grammar g;
    grammar_init(&g);

    int kids[2];
    kids[0] = node_lit(&g, "ab", 2);
    kids[1] = node_lit(&g, "cd", 2);
    int seq = node_seq(&g, kids, 2);
    grammar_add_rule(&g, seq);

    MatchResult r;
    r = parse(&g, "abcd", 4);
    check("seq match", r.ok && r.consumed == 4);

    r = parse(&g, "abce", 4);
    check("seq fail mid", !r.ok);

    r = parse(&g, "ab", 2);
    check("seq fail short", !r.ok);
}

/* ---- Test 4: ordered choice ---- */
static void test_choice(void) {
    Grammar g;
    grammar_init(&g);

    int kids[2];
    kids[0] = node_lit(&g, "cat", 3);
    kids[1] = node_lit(&g, "car", 3);
    int ch = node_choice(&g, kids, 2);
    grammar_add_rule(&g, ch);

    MatchResult r;
    r = parse(&g, "cat", 3);
    check("choice first", r.ok && r.consumed == 3);

    r = parse(&g, "car", 3);
    check("choice second", r.ok && r.consumed == 3);

    r = parse(&g, "cap", 3);
    check("choice neither", !r.ok);
}

/* ---- Test 5: star (zero or more) ---- */
static void test_star(void) {
    Grammar g;
    grammar_init(&g);

    int digit = node_range(&g, '0', '9');
    int stars = node_star(&g, digit);
    grammar_add_rule(&g, stars);

    MatchResult r;
    r = parse(&g, "12345", 5);
    check("star multiple", r.ok && r.consumed == 5);

    r = parse(&g, "abc", 3);
    check("star zero", r.ok && r.consumed == 0);

    r = parse(&g, "", 0);
    check("star empty", r.ok && r.consumed == 0);
}

/* ---- Test 6: plus (one or more) ---- */
static void test_plus(void) {
    Grammar g;
    grammar_init(&g);

    int digit = node_range(&g, '0', '9');
    int pl = node_plus(&g, digit);
    grammar_add_rule(&g, pl);

    MatchResult r;
    r = parse(&g, "12345", 5);
    check("plus multiple", r.ok && r.consumed == 5);

    r = parse(&g, "abc", 3);
    check("plus fail zero", !r.ok);

    r = parse(&g, "7", 1);
    check("plus single", r.ok && r.consumed == 1);
}

/* ---- Test 7: optional ---- */
static void test_opt(void) {
    Grammar g;
    grammar_init(&g);

    int q = node_lit(&g, "?", 1);
    int oq = node_opt(&g, q);
    grammar_add_rule(&g, oq);

    MatchResult r;
    r = parse(&g, "?", 1);
    check("opt present", r.ok && r.consumed == 1);

    r = parse(&g, "!", 1);
    check("opt absent", r.ok && r.consumed == 0);
}

/* ---- Test 8: negative lookahead ---- */
static void test_not(void) {
    Grammar g;
    grammar_init(&g);

    int bang = node_lit(&g, "!", 1);
    int nbang = node_not(&g, bang);
    grammar_add_rule(&g, nbang);

    MatchResult r;
    r = parse(&g, "?", 1);
    check("not succeeds", r.ok && r.consumed == 0);

    r = parse(&g, "!", 1);
    check("not fails when present", !r.ok);
}

/* ---- Test 9: rule reference ---- */
static void test_ref(void) {
    Grammar g;
    grammar_init(&g);

    int digit = node_range(&g, '0', '9');
    int r0 = grammar_add_rule(&g, digit);

    int ref0 = node_ref(&g, r0);
    grammar_add_rule(&g, ref0);

    MatchResult r;
    r = parse(&g, "5", 1);
    check("ref match", r.ok && r.consumed == 1);

    r = parse(&g, "a", 1);
    check("ref mismatch", !r.ok);
}

/* ---- Test 10: combined grammar (simple arithmetic) ---- */
static void test_arithmetic(void) {
    Grammar g;
    grammar_init(&g);

    /* digit = [0-9]+ */
    int d = node_range(&g, '0', '9');
    int digit = node_plus(&g, d);
    int r_digit = grammar_add_rule(&g, digit);

    /* number = digit */
    int ref_d = node_ref(&g, r_digit);
    int r_number = grammar_add_rule(&g, ref_d);

    /* addop = '+' / '-' */
    int plus = node_lit(&g, "+", 1);
    int minus = node_lit(&g, "-", 1);
    int kids2[2] = {plus, minus};
    int addop = node_choice(&g, kids2, 2);

    /* term = number (addop number)* */
    int ref_num1 = node_ref(&g, r_number);
    int rhs[2] = {addop, ref_num1};
    int one_add = node_seq(&g, rhs, 2);
    int many_add = node_star(&g, one_add);
    int ref_num2 = node_ref(&g, r_number);
    int term_parts[2] = {ref_num2, many_add};
    int term = node_seq(&g, term_parts, 2);
    int r_term = grammar_add_rule(&g, term);

    /* expr = term */
    int ref_term = node_ref(&g, r_term);
    int r_expr = grammar_add_rule(&g, ref_term);

    ParseState st;
    MatchResult r;

    /* Test number rule */
    st.input.buf = "123"; st.input.len = 3;
    st.pos = 0; st.max_pos = 0; st.depth = 0;
    r = match(&g, &st, g.rule_starts[r_number]);
    check("arith number", r.ok && r.consumed == 3);

    /* Test term rule */
    st.pos = 0; st.max_pos = 0; st.depth = 0;
    r = match(&g, &st, g.rule_starts[r_term]);
    check("arith term simple", r.ok && r.consumed == 3);

    st.input.buf = "1+2"; st.input.len = 3;
    st.pos = 0; st.max_pos = 0; st.depth = 0;
    r = match(&g, &st, g.rule_starts[r_term]);
    check("arith term add", r.ok && r.consumed == 3);

    st.input.buf = "1+2-3"; st.input.len = 5;
    st.pos = 0; st.max_pos = 0; st.depth = 0;
    r = match(&g, &st, g.rule_starts[r_term]);
    check("arith term mixed", r.ok && r.consumed == 5);

    /* Test expr rule (via parse, using rule_starts[0] swap) */
    /* Actually, just test via match directly */
    st.input.buf = "42+7"; st.input.len = 4;
    st.pos = 0; st.max_pos = 0; st.depth = 0;
    r = match(&g, &st, g.rule_starts[r_expr]);
    check("arith expr", r.ok && r.consumed == 4);
}

/* ---- Test 11: nested sequence in choice ---- */
static void test_nested(void) {
    Grammar g;
    grammar_init(&g);

    int a = node_lit(&g, "aa", 2);
    int b = node_lit(&g, "bb", 2);
    int kids[2] = {a, b};
    int ch = node_choice(&g, kids, 2);

    /* star of choice */
    int stars = node_star(&g, ch);
    grammar_add_rule(&g, stars);

    MatchResult r;
    r = parse(&g, "aabb", 4);
    check("nested star-choice", r.ok && r.consumed == 4);

    r = parse(&g, "aab", 3);
    check("nested partial", r.ok && r.consumed == 2);

    r = parse(&g, "xyz", 3);
    check("nested empty match", r.ok && r.consumed == 0);
}

int main(void) {
    printf("PEG engine tests:\n");

    test_literal();
    test_range();
    test_sequence();
    test_choice();
    test_star();
    test_plus();
    test_opt();
    test_not();
    test_ref();
    test_arithmetic();
    test_nested();

    printf("  %d/%d passed\n", tests_passed, tests_run);
    return tests_passed == tests_run ? 0 : 1;
}
