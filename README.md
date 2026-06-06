# LR(0) Parser Visualiser

> An interactive, GUI-based tool for building and visualising LR(0) parsers — from grammar input to parse tree — built with Python.

---

## What is this?

The **LR(0) Parser Visualiser** takes any context-free grammar and walks you through the entire LR(0) parser construction process — step by step, visually. It builds the canonical collection of LR(0) item sets (the DFA), constructs the ACTION/GOTO parsing table, detects conflicts, and lets you parse any input string while watching the stack, transitions, and parse tree come to life in real time.

Built as a Compiler Construction project, this tool is designed to make the theory tangible — great for learning, teaching, or debugging grammars.

---

## Features

### Core Parser Engine
- **DFA Construction** — Closure, GOTO, and canonical collection algorithms following the Dragon Book. Every state (I0, I1, …) is displayed with its kernel items, closure items, and outgoing transitions.
- **ACTION/GOTO Table** — Full parsing table with conflict detection. Both shift/reduce and reduce/reduce conflicts are identified and highlighted in red.
- **Augmented Grammar** — Automatically adds `S' → S` and re-numbers all productions.
- **ε-production Support** — Empty productions are parsed and reduced correctly as zero-pop reductions.

### Interactive GUI (6 Tabs)
| Tab | What it does |
|-----|-------------|
| **Grammar** | Type or select a built-in grammar, then click 🔨 Build Parser |
| **States (Items)** | Textbook-style listing of every LR(0) item set |
| **DFA Diagram** | Visual diagram with zoom, pan, and export (PNG / PDF / SVG) |
| **Parsing Table** | Full ACTION + GOTO table; conflict cells highlighted in red |
| **Parse Input** | Run the parser in full or step-by-step mode |
| **Parse Tree** | Derivation tree drawn graphically after a successful parse |

### Step-Through & Visualisation
- **Step-by-step animation** — Walk through the parse one move at a time. The DFA tab highlights the current state in yellow.
- **Parse tree** — A graphical derivation tree is drawn after every successful parse.
- **Colour-coded trace** — Shift, reduce, accept, and error rows are colour-coded for easy reading.
- **Save DFA** — Export the automaton diagram as PNG, PDF, or SVG from the toolbar.

### Built-in Example Grammars
Five ready-to-use grammars are bundled — including ε-productions and a deliberately non-LR(0) grammar so you can explore conflict detection straight away.

### Unit Tests
`tests.py` includes 13 unit tests covering grammar parsing, the Dragon Book example, conflict detection, and the parentheses grammar.

---

## Algorithm References

All algorithms follow the **Dragon Book** (*Compilers: Principles, Techniques, and Tools* — Aho, Lam, Sethi, Ullman, 2nd edition):

| Algorithm                        | Section           |
|----------------------------------|-------------------|
| Closure of an item set           | §4.6.2, Fig. 4.32 |
| GOTO function                    | §4.6.2, Fig. 4.32 |
| Canonical LR(0) collection       | §4.6.2, Fig. 4.33 |
| LR(0) parsing table construction | §4.6.3, Fig. 4.35 |
| FIRST and FOLLOW sets            | §4.4.2            |
| SLR(1) refinement                | §4.6.4, Fig. 4.40 |
| Shift-reduce parsing algorithm   | §4.5.3, Fig. 4.36 |

> **Note on the parsing table:** The DFA and item sets are pure LR(0). Reduce actions use the SLR(1) refinement — a reduction `A → α` is added to `ACTION[I, t]` only when `t ∈ FOLLOW(A)`. This is the standard construction used in every modern compiler textbook and matches tools like `lr0parser.com`.

---

## Project Structure

```
lr0_parser/
├── main.py              ← Entry point — run this to launch the visualiser
├── grammar.py           ← Parses grammar text into augmented productions
├── lr0_automaton.py     ← LR(0) items, closure, GOTO, canonical collection
├── parsing_table.py     ← ACTION + GOTO table construction and conflict detection
├── parser_engine.py     ← Shift-reduce simulation and parse-tree builder
├── gui.py               ← tkinter GUI (6 tabs)
├── tests.py             ← Unit tests for the algorithm
├── requirements.txt     ← Dependencies: matplotlib, networkx
├── README.md            ← You are here
└── examples/
    └── grammars.txt     ← Bundled example grammars
```

> The GUI calls into the algorithm modules but contains **no parsing logic** — the separation is intentional so the algorithm can be studied and tested independently of the interface.

---

## Requirements

- **Python 3.10 or newer**
- **tkinter** (ships with the official Python installer on Windows and macOS)
- `matplotlib` and `networkx` (installed via `requirements.txt`)

### Linux — tkinter setup

If `import tkinter` fails on Linux, install it via your package manager:

```bash
# Ubuntu / Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

---

## Getting Started

### Option A — PyCharm

1. **Open the project** — *File → Open* → select the `lr0_parser` folder. Click *Trust* when prompted.
2. **Create a virtual environment** — *File → Settings → Project → Python Interpreter → Add Interpreter → Add Local Interpreter → Virtualenv → New*. Choose Python 3.10+.
3. **Install dependencies** — PyCharm will detect `requirements.txt` and offer to install automatically. Accept, or run in the terminal:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the app** — Right-click `main.py` → *Run 'main'*. Use the green ▶ button from then on.
5. **Run the tests** — Right-click `tests.py` → *Run 'Unittests in tests.py'*. All 13 tests should pass.

### Option B — Terminal

```bash
cd lr0_parser

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# or:  .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Launch the visualiser
python main.py
```

---

## How to Use the Visualiser

1. **Grammar tab** — Type a context-free grammar or choose one of the five built-in examples. Click **🔨 Build Parser**. The right pane shows the augmented grammar with productions numbered (0, 1, 2, …) — these numbers map to the `r0`, `r1`, … entries in the parsing table.

2. **States tab** — Textbook listing of every state I0, I1, …. Each state shows its kernel items first, then closure items, then the GOTO transitions out of that state.

3. **DFA Diagram tab** — Visual automaton diagram. Blue = ordinary state, green double-circle = accept state, yellow = the state currently being executed during step-through. Use the matplotlib toolbar to zoom or pan, or click **Save DFA as PNG…** to export.

4. **Parsing Table tab** — Full ACTION + GOTO table.
   - `s5` → shift to state 5
   - `r3` → reduce by production 3 (cross-reference with the Grammar tab)
   - `acc` → accept
   - `s5/r3` → conflict (the cell holds two actions); the row turns red.

5. **Parse Input tab** — Type any input string.
   - **▶ Parse all** — runs the full parse and dumps the complete trace.
   - **⏮ Reset / Load** — loads the string but waits for you to step through.
   - **⏭ Next step** — advances one step at a time. Watch the DFA tab to track the current state.

6. **Parse Tree tab** — After a successful parse, the full derivation tree is drawn graphically here.

---

## License

Free for educational use — modify and extend as you like.