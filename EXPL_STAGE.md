# Stage 1: The META II Metacompiler
### *A Senior-to-Junior Developer Guide to Parsing magic*

---

## 1. Welcome to the Team! 👋
Hey there! Welcome to the compiler project. Since you're jumping into **Stage 1 (Metacompiler)**, I want to take a moment to set you up for success. 

This stage is usually the one that makes people's brains do a little backflip. If you've taken a compiler class, you probably expect us to start writing a massive, 2000-line hand-crafted tokenizer and a recursive descent parser with `if (token == IF_KW) { match(IF_KW); ... }` everywhere. 

**Forget that.** We are not building a parser the tedious way. We are building a *Metacompiler*. 

Instead of writing code that parses C, we are going to write a tiny **META II-style pattern-matching engine**. This engine reads a compact text file of syntax rules, recognizes input with PEG-style ordered choice/backtracking, and attaches output actions to rules. This is the paradigm pioneered by **Val Schorre (META II)** and later explored in small-language systems like **Alan Kay's VPRI STEPS** work.

The important design choice: **META II is the model, PEG is the matching discipline.** We use META II's grammar-plus-output-action logic, while using modern PEG-style deterministic alternatives to keep behavior predictable.

Grab a coffee, and let's break down how this works!

---

## 2. The Big Picture: Why a Metacompiler?

Let's compare the traditional way of writing parsers with our metacompiler approach.

```
TRADITIONAL METHOD (Hand-Written Parser)
+------------------+     +--------------------+     +-------------+
| C Source Code    | --> | Hand-Written Lexer | --> | Hand-Written| --> AST
| (e.g. main.c)    |     | (300 lines of code)|     | Parser (2k) |
+------------------+     +--------------------+     +-------------+
  Issues: Fragile, painful to modify, massive codebase.

OUR METHOD (META II-style Metacompiler)
+------------------+
| Grammar File     |---\
| (e.g. c.peg)     |    \
+------------------+     v
                     +-----------------------+     +---------------+
                     | Stage 1 META II Core  | --> | Parser Engine |
                     | (Parser-Generator)    |     | (Auto-Gen)    |
                     +-----------------------+     +---------------+
                                                          |
  +------------------+                                    v
  | C Source Code    | --------------------------------> AST
  +------------------+
  Benefits: Change the language in 5 seconds by editing the grammar file.
```

By building a pattern matcher that reads a formal definition of language syntax, we make our actual parser incredibly brief and declarative. 

In META II terms, a grammar rule has two jobs:

```text
rule = pattern-to-recognize .OUT(output-to-produce) ;
```

For SMGCC, early output actions should produce AST nodes. Later stages can emit lower-level compiler structures.

---

## 3. The Mind-Bending Self-Hosting Bootstrap Loop

Here is the real beauty of a metacompiler. How do we parse our grammar files? **We use the metacompiler to compile its own grammar definition!**

Take a look at this loop:

```
                  +-------------------------------------------------+
                  |                                                 |
                  v                                                 |
         +-----------------+                                        |
         |  meta.peg       |                                        |
         |  (The grammar   |                                        |
         |   of Grammars)  |                                        |
         +-----------------+                                        |
                  |                                                 |
                  | (Parsed by)                                     |
                  v                                                 |
         +-----------------+                                        |
         | Metacompiler    |                                        |
         | (Runs engine)   |                                        |
         +-----------------+                                        |
                  |                                                 |
                  | (Generates a new, optimized)                     |
                  v                                                 |
         +-----------------+                                        |
         | Compiled Parser | ---------------------------------------+
         | (Executable)    |
         +-----------------+
```

1. We define the syntax rules of our grammar language *in that language itself* (we call it `meta.peg`).
2. We feed `meta.peg` into our initial bootstrap metacompiler.
3. It generates the code for a parser.
4. That generated parser is now our *new* metacompiler!

Once this loop closes, we can extend our language, add complex parsing operators, and update our parser generator simply by editing `meta.peg`. It's incredibly satisfying once you see it work.

---

## 4. META II Rules With PEG-Style Matching

Before we look at the code, let's understand the subset we need. META II gives us the metacompiler shape: named rules, pattern matching, and output actions. PEG gives us deterministic matching rules: ordered alternatives, backtracking, and lookahead.

Here are the core operators our pattern-matching engine must support:

### A. Ordered Choice (`/`)
In traditional CFGs, `A | B` means both `A` and `B` are equal alternatives, which can lead to ambiguity (e.g., the dangling-else problem).
In PEG, we write `A / B`. This means: **"Try to match A. If A succeeds, consume input and stop. Only if A fails, backtrack and try B."**
Order matters! 

```
Rule:   keyword  = 'if' / 'identifier'
Input:  "if" -> Matches 'if'.
Input:  "iffy" -> Matches 'if', leaving "fy" in the stream. (A classic pitfall we'll solve!)
```

### B. Lookahead Operators (`&` and `!`)
Lookaheads let us check ahead in the input stream *without* consuming any text.
- **Positive Lookahead (`&expr`):** Matches if `expr` matches, but does not advance the cursor.
- **Negative Lookahead (`!expr`):** Matches if `expr` does **not** match. 

This is incredibly useful to prevent keywords from being treated as identifiers:
```
Rule:   if_statement = 'if' !identifier_char
```
If the input is `iffy`, `if` matches, but the negative lookahead `!identifier_char` fails because `f` is an identifier character. This correctly rejects `iffy` as an `if` keyword.

### C. Repetition (`*`, `+`, `?`)
- `expr*`: Zero or more matches (greedy, consumes as much as possible).
- `expr+`: One or more matches.
- `expr?`: Optional match (zero or one).

### D. Output Actions (`.OUT(...)`)
META II rules can produce output while they match. We keep this idea, but the first useful output target is an AST node, not raw assembly.

```text
number = digit+ .OUT(Number(text)) ;
factor = number / '(' expression ')' ;
term   = factor (('*' / '/') factor)* .OUT(BinaryTree(...)) ;
```

The syntax above is illustrative. The final DSL can be smaller, but it must preserve the idea that output is attached to grammar rules.

---

## 5. Under the Hood: The Backtracking Machine

How does a pattern matcher run these rules? Under the hood, it is a state machine that tracks a cursor position in the input string.

Let's trace how the rule `assignment = identifier '=' expression` parses the string `"x = 42"`:

```
INPUT: "x = 42"
CURSOR: ^ (index 0)

1. Try rule 'identifier'
   - Checks if 'x' is a valid identifier.
   - Match SUCCESS. 
   - CURSOR moves to index 1: " = 42"
                              ^

2. Consume optional whitespace (implicit or explicit in rules)
   - CURSOR moves to index 2: "= 42"
                               ^

3. Try matching literal '='
   - Char at cursor is '='.
   - Match SUCCESS.
   - CURSOR moves to index 3: " 42"
                               ^

4. Consume whitespace
   - CURSOR moves to index 4: "42"
                               ^

5. Try rule 'expression'
   - Traces digit pattern matching.
   - Match SUCCESS ("42").
   - CURSOR moves to index 6: (end of string)

6. Whole rule 'assignment' returns SUCCESS!
```

### What if a match fails? **Backtracking!**
If we are parsing a rule like `type = 'int' / 'void'`, and our input is `"void"`.
1. The engine tries `'int'`. It matches `'v'`? No. Fail.
2. The engine **backtracks** (resets its cursor index back to where it was before trying `'int'`).
3. The engine tries `'void'`. Match SUCCESS! Cursor advances.

---

## 6. Engineering the Metacompiler: Core Architecture

When you start implementing this in code, you'll want to represent the grammar rules as structured classes/types and write an interpreter (or generator) that executes them. 

Here is a junior-friendly blueprint of our types and matcher interfaces.

### Core Data Structures
We need a structure to represent the pattern matching environment:

```typescript
// Tracking state during parse
interface ParseState {
  input: string;      // The raw source code we are parsing
  cursor: number;     // Current character index in input
  maxPosition: number;// Deepest position reached (crucial for error messages!)
}

// Every parsing rule resolves to a match outcome
type MatchResult = 
  | { success: true;  consumed: number; value: any }
  | { success: false; reason: string }
```

### The AST Representation of Rules
The META II engine will process grammar rules. We can represent rules as node types:

```typescript
type MetaNode =
  | { type: 'terminal'; value: string }                 // Literal e.g., "if"
  | { type: 'character_range'; start: string; end: string } // [a-z]
  | { type: 'sequence'; expressions: MetaNode[] }         // Rule A followed by Rule B
  | { type: 'ordered_choice'; expressions: MetaNode[] }   // A / B
  | { type: 'zero_or_more'; expression: MetaNode }        // A*
  | { type: 'negative_lookahead'; expression: MetaNode }  // !A
  | { type: 'rule_reference'; name: string }             // Reference to another rule
  | { type: 'output_action'; name: string; args: string[] } // .OUT(...) style action
```

### The Matching Engine Loop
Our engine runs a recursive matching loop. Here's the high-level pseudocode of how you implement the matchers:

```typescript
function matchNode(node: MetaNode, state: ParseState): MatchResult {
  switch (node.type) {
    case 'terminal': {
      const matchLength = node.value.length;
      const snippet = state.input.substring(state.cursor, state.cursor + matchLength);
      if (snippet === node.value) {
        state.cursor += matchLength;
        return { success: true, consumed: matchLength, value: snippet };
      }
      return { success: false, reason: `Expected '${node.value}'` };
    }

    case 'ordered_choice': {
      const savedCursor = state.cursor;
      for (const subExpr of node.expressions) {
        const result = matchNode(subExpr, state);
        if (result.success) {
          return result; // Take the first choice that succeeds!
        }
        // Fail! Backtrack cursor and try the next choice
        state.cursor = savedCursor;
      }
      return { success: false, reason: "All choices failed" };
    }

    case 'sequence': {
      const savedCursor = state.cursor;
      const accumulatedValues = [];
      for (const subExpr of node.expressions) {
        const result = matchNode(subExpr, state);
        if (!result.success) {
          // One step failed, so the whole sequence fails! Backtrack!
          state.cursor = savedCursor;
          return { success: false, reason: result.reason };
        }
        accumulatedValues.push(result.value);
      }
      return { success: true, consumed: state.cursor - savedCursor, value: accumulatedValues };
    }
    
    // ... we will implement other cases (zero_or_more, lookaheads, etc.) in Stage 1!
  }
}
```

---

## 7. Senior Pro-Tips & Common Pitfalls

Since I've been down this road before, let me give you three golden rules to keep you out of trouble while implementing Stage 1:

### 1. Left Recursion is Deadly 🛑
In standard PEG, rules cannot call themselves recursively as the very first element.
For example, this rule will cause an infinite loop and crash your stack:
```peg
expr = expr '+' term / term
```
Why? To match `expr`, the engine tries to match `expr` first, which tries to match `expr` first, forever!
**The fix:** Rewrite left recursion using repetition loops:
```peg
expr = term ('+' term)*
```
This parses a term first, and then zero or more trailing addition operations. It's completely stack-safe!

### 2. Handle Whitespace Implicitly or Systematically 🧹
C source code is loaded with spaces, tabs, and comments. If you force every rule to match spaces manually (like `expr = identifier spacing '=' spacing term`), your grammar will look like alphabet soup.
*Design choice:* Have our lexer/matcher rules automatically skip whitespaces after successfully matching a core token (such as identifiers, keywords, or operators). 

### 3. Build Detailed Parse Errors Early 📍
When parsing fails in a large file, simply saying `"Parse Failed"` is incredibly frustrating. 
*Pro-tip:* In your `ParseState`, track `maxPosition` (the furthest index the engine ever reached in the input string). If the entire parse fails, the syntax error is almost always located at `maxPosition`. Map that index to a line/column number, and print out that line of code with a little caret (`^`) pointing to the spot. The team will thank you!

---

## 8. Your Mission in Stage 1

Now that you have the mental model, here is what we are going to build when we start Stage 1:

1. **The META II Matcher Engine:** Implement pattern-matching types, recursive parser loop, backtracking logic, and output-action hooks.
2. **The Meta-Grammar:** Write the grammar that specifies the META II-style grammar language itself.
3. **The Bootstrap:** Feed the meta grammar into the matcher to generate our parser parser.

If any of this feels overwhelming, don't sweat it. We are going to build this piece-by-piece, with **TDD guiding every single step**. 

You're going to do great. Let's make a compiler! 🚀
