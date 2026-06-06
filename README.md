# LR(0) Parser Visualiser

A complete LR(0) parser-construction tool with an interactive GUI,
written in Python. Built for the *Compiler Construction* semester project.

The tool takes any context-free grammar, builds the canonical collection
of LR(0) item sets (the DFA), constructs the ACTION/GOTO parsing table,
detects shift/reduce and reduce/reduce conflicts, and lets you parse
arbitrary input strings step by step — visualising the stack, the
remaining input, the state transitions, and the resulting parse tree.

---

## Features (mapped to the grading rubric)

| Rubric criterion                                  | How the project covers it                                                          |
|--------------------------------------------------|------------------------------------------------------------------------------------|
| **DFA construction (3 marks)**                   | Closure / GOTO / canonical collection algorithm in `lr0_automaton.py`. Every state is shown both textually (with kernel + closure items, like a textbook) and as an interactive diagram. Numbered I0, I1, … |
| **Parsing table (4 marks)**                      | Full ACTION + GOTO table in `parsing_table.py`. Conflicts are detected and reported. Both shift/reduce and reduce/reduce. Cells with conflicts are highlighted in red. |
| **GUI implementation (3 marks)**                 | 6-tab tkinter GUI in `gui.py`. Multiple inputs, accept/reject decisions, lexical-error messages, syntax-error messages, and step-by-step animation that highlights the current DFA state. |
| **CCP requirements** (non-trivial grammar, multiple inputs, error handling) | Five built-in example grammars including ε-productions and a deliberately non-LR(0) grammar so you can demonstrate conflict detection. Tokeniser handles both whitespace-separated and packed-character input. |

### Beyond the rubric (improvements added)

- **Parse-tree visualisation** — after a successful parse, the derivation tree is drawn graphically.
- **Step-through mode** — *Reset → Next step* walks through the parse one move at a time. The DFA tab highlights the current state in yellow.
- **Conflict detection & classification** — distinguishes shift/reduce from reduce/reduce; lists every conflict with state and symbol.
- **Augmented grammar display** — shows `S' → S` and re-numbers all productions.
- **ε-production support** — empty productions parsed correctly and reduced as 0-pop reductions.
- **Save DFA as PNG / PDF / SVG** — one click from the DFA tab toolbar.
- **Save-friendly output** — colour-coded trace rows (shift / reduce / accept / error) and double-circle accept states.
- **Unit tests** — `tests.py` covers Grammar parsing, Dragon-Book example, conflict detection, and parens grammar.

---

## File layout

```
lr0_parser/
├── main.py              ← entry point (run this)
├── grammar.py           ← Grammar text → augmented productions
├── lr0_automaton.py     ← LR(0) items, closure, GOTO, canonical collection
├── parsing_table.py     ← ACTION + GOTO + conflict detection
├── parser_engine.py     ← shift-reduce simulation + parse-tree builder
├── gui.py               ← tkinter GUI (6 tabs)
├── tests.py             ← unit tests for the algorithm
├── requirements.txt     ← matplotlib, networkx
├── README.md            ← (this file)
└── examples/
    └── grammars.txt     ← bundled example grammars
```

The GUI calls into the algorithm modules but contains *no parsing logic*
itself — the separation is intentional so the algorithm can be graded
independently of the UI.

---

## Setting up in PyCharm

1. **Open the project**
   - Launch PyCharm → *File → Open* → select the `lr0_parser` folder.
   - When prompted to "Trust the project", click *Trust*.

2. **Create a virtual environment (recommended)**
   - *File → Settings → Project: lr0_parser → Python Interpreter*.
   - Click the gear icon → *Add Interpreter → Add Local Interpreter*.
   - Choose *Virtualenv Environment → New*.
   - Pick Python 3.10 or newer. Click *OK*.

3. **Install the dependencies**
   - PyCharm should automatically detect `requirements.txt` and offer to
     install. Accept.
   - Or open *Terminal* (bottom of PyCharm) and run:
     ```
     pip install -r requirements.txt
     ```

4. **Mark `main.py` as the run target**
   - Right-click `main.py` in the project tree → *Run 'main'*.
   - PyCharm creates a run configuration. From now on, the green ▶ button
     at the top right launches the visualiser.

5. **Run the unit tests**
   - Right-click `tests.py` → *Run 'Unittests in tests.py'*.
   - You should see "Ran 13 tests in … OK".

> **tkinter** ships with the official Python installer on Windows, macOS,
> and most Linux distributions. If you are on Linux and `import tkinter`
> fails, install it via your package manager:
>   - Ubuntu/Debian: `sudo apt install python3-tk`
>   - Fedora:       `sudo dnf install python3-tkinter`
>   - Arch:         `sudo pacman -S tk`

---

## Running from a plain terminal (no PyCharm)

```bash
cd lr0_parser
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# or:  .venv\Scripts\activate     # Windows
pip install -r requirements.txt
python main.py
```

---

## Using the visualiser

1. **Tab 1 — Grammar.** Type or pick an example grammar.
   Click **🔨 Build Parser**. The right pane shows the augmented grammar
   with productions numbered (0, 1, 2, …); these are the numbers that
   appear in `r0`, `r1`, … in the parsing table.

2. **Tab 2 — States (Items).** Textbook listing of every state I0, I1, …
   Each state lists its kernel items first, then its closure items, and
   below them the GOTO transitions out of that state.

3. **Tab 3 — DFA Diagram.** Visual diagram. Blue = ordinary state,
   green double-circle = accept state, yellow = the state currently
   being executed (during step-through). Use the matplotlib toolbar
   to zoom/pan, or click *Save DFA as PNG…* to export.

4. **Tab 4 — Parsing Table.** Full ACTION + GOTO table.
   - `s5` = shift to state 5
   - `r3` = reduce by production 3 (look up the number in tab 1)
   - `acc` = accept
   - Cells like `s5/r3` mean the cell holds *two* actions — that's an
     LR(0) conflict and the row turns red.

5. **Tab 5 — Parse Input.** Type a string in the input field.
   - **▶ Parse all** — runs the parser and dumps the entire trace.
   - **⏮ Reset / Load** — loads the trace but shows nothing yet.
   - **⏭ Next step** — replays one step at a time. Watch the DFA tab
     to see which state is being executed.

6. **Tab 6 — Parse Tree.** After a successful parse, the derivation
   tree is drawn here.

---

## Algorithm references

All algorithms follow *Compilers: Principles, Techniques, and Tools*
(Aho, Lam, Sethi, Ullman — the "Dragon Book"), 2nd edition:

- Closure of an item set: §4.6.2, Fig. 4.32.
- GOTO function: §4.6.2, Fig. 4.32.
- Canonical collection of LR(0) item sets: §4.6.2, Fig. 4.33.
- LR(0) parsing table construction: §4.6.3, Fig. 4.35.
- FIRST and FOLLOW sets: §4.4.2.
- SLR refinement (reduce only on FOLLOW lookaheads): §4.6.4, Fig. 4.40.
- Shift-reduce parsing algorithm: §4.5.3, Fig. 4.36.

**Note on the parsing table.** The DFA and item sets are pure LR(0).
Reduce actions are placed using the SLR(1) refinement: a reduction
`A → α` is added to `ACTION[I, t]` only when `t ∈ FOLLOW(A)`, instead
of for every terminal. This is the construction presented in every
modern compiler textbook (because pure LR(0) is too weak to handle
the standard expression grammar) and matches what tools like
`lr0parser.com` produce.

---

## License

Educational use, free to modify and extend.
