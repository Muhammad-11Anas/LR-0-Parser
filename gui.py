"""
gui.py
======
Tkinter GUI for the LR(0) parser visualiser.

Tabs:
    1. Grammar            – input the grammar; shows the augmented grammar.
    2. States (Items)     – textbook-style listing of every LR(0) item set.
    3. DFA Diagram        – drawn with networkx + matplotlib, one node per state.
    4. Parsing Table      – ACTION + GOTO in a single Treeview.
    5. Parse Input        – step-by-step shift-reduce trace for a given string.
    6. Parse Tree         – derivation tree drawn after a successful parse.

All visualisations are read directly from the algorithm modules — no logic
lives in the GUI, only presentation.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)
from matplotlib.patches import FancyBboxPatch
import networkx as nx

from grammar import Grammar
from lr0_automaton import LR0Automaton
from parsing_table import ParsingTable
from parser_engine import ParserEngine, ParseNode


# ---------------------------------------------------------------------------
# Bundled example grammars
# ---------------------------------------------------------------------------
EXAMPLES = {
    "1) Dragon Book — S → C C, C → c C | d": (
        "S -> C C\nC -> c C | d",
        "c c d d",
    ),
    "2) Expressions — E → E + T | T ; T → T * F | F ; F → ( E ) | id": (
        "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
        "( id + id ) * id",
    ),
    "3) Lists — L → L , E | E ; E → a | b": (
        "L -> L , E | E\nE -> a | b",
        "a , b , a",
    ),
    "4) Parentheses — S → ( S ) | a": (
        "S -> ( S ) | a",
        "( ( a ) )",
    ),
    "5) Conflict demo — dangling else  (NOT LR(0))": (
        "S -> i S e S | i S | a",
        "i i a e a",
    ),
    "6) ε production — S → A b ; A → a A | ε": (
        "S -> A b\nA -> a A | ε",
        "a a b",
    ),
}


# ---------------------------------------------------------------------------
class LR0ParserApp:
    PALETTE = {
        "primary": "#2563eb",
        "primary_dark": "#1e40af",
        "success": "#16a34a",
        "danger": "#dc2626",
        "warning": "#d97706",
        "neutral": "#475569",
        "node_default": "#dbeafe",
        "node_accept": "#bbf7d0",
        "node_current": "#fde68a",
        "node_border": "#1e293b",
        "edge": "#334155",
        "edge_label_bg": "#fef3c7",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LR(0) Parser Visualiser")
        self.root.geometry("1280x820")
        self.root.minsize(1000, 700)

        # State of the application
        self.grammar: Grammar | None = None
        self.automaton: LR0Automaton | None = None
        self.table: ParsingTable | None = None
        self.engine: ParserEngine | None = None

        # Step-through state for the Parse tab
        self.last_steps = []
        self.last_accepted = False
        self.last_error: str | None = None
        self.last_tree: ParseNode | None = None
        self.current_step_idx = -1

        self._configure_style()
        self._build_layout()

    # ------------------------------------------------------------------
    # Style and layout
    # ------------------------------------------------------------------
    def _configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"),
                        foreground=self.PALETTE["primary_dark"])
        style.configure("Heading.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Treeview", font=("Consolas", 10), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _build_layout(self):
        header = ttk.Frame(self.root, padding=(15, 10, 15, 5))
        header.pack(fill="x")

        ttk.Label(header, text="LR(0) Parser Visualiser",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(header,
                  text="    Build the parser → inspect states/DFA/table → parse a string",
                  foreground=self.PALETTE["neutral"]).pack(side="left", padx=10)

        # Persistent status banner (initially hidden until first build).
        # Shows whether the grammar is LR(0) or has conflicts.
        self.banner_frame = tk.Frame(self.root, bg="#475569")
        self.banner_label = tk.Label(
            self.banner_frame, text="",
            bg="#475569", fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15, pady=8, anchor="w", justify="left",
            wraplength=1400,
        )
        self.banner_label.pack(fill="x")
        # not packed yet

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        self._build_tab_grammar()
        self._build_tab_states()
        self._build_tab_dfa()
        self._build_tab_table()
        self._build_tab_parser()
        self._build_tab_tree()

        self.status_var = tk.StringVar(
            value="Ready. Pick an example or enter a grammar, then press Build Parser."
        )
        ttk.Label(self.root, textvariable=self.status_var, anchor="w",
                  relief="sunken", padding=(8, 4)).pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    def _set_banner(self, kind: str, message: str):
        """kind: 'success' | 'warning' | 'error' | 'hidden'."""
        if kind == "hidden":
            self.banner_frame.pack_forget()
            return
        colors = {
            "success": "#16a34a",  # green
            "warning": "#d97706",  # amber
            "error":   "#dc2626",  # red
        }
        bg = colors.get(kind, "#475569")
        self.banner_frame.config(bg=bg)
        self.banner_label.config(bg=bg, text=message)
        # Re-pack just below the header
        self.banner_frame.pack_forget()
        self.banner_frame.pack(fill="x", padx=10, pady=(0, 4),
                               before=self.notebook)

    # ------------------------------------------------------------------
    # Tab 1: Grammar
    # ------------------------------------------------------------------
    def _build_tab_grammar(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=" 1. Grammar ")

        # left: input
        left = ttk.LabelFrame(frame, text="Grammar input", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        instructions = (
            "• One production per line.    • Format:    LHS  ->  RHS1 | RHS2\n"
            "• Spaces between symbols are OPTIONAL when symbols are punctuation:\n"
            "    E -> E + T | T    AND    E->E+T|T    both work.\n"
            "• For single-letter alphabets like  S -> a S b , spaces ARE required.\n"
            "• Use 'ε' or '#' for epsilon.    • First non-terminal = start symbol.\n"
            "• Lines beginning with # are treated as comments."
        )
        ttk.Label(left, text=instructions, justify="left",
                  foreground=self.PALETTE["neutral"]).pack(anchor="w", pady=(0, 6))

        self.grammar_text = scrolledtext.ScrolledText(
            left, height=14, font=("Consolas", 12), wrap="none",
            background="#f8fafc"
        )
        self.grammar_text.pack(fill="both", expand=True)
        self.grammar_text.insert("1.0", "S -> C C\nC -> c C | d\n")

        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=(8, 0))

        ttk.Button(controls, text="🔨  Build Parser",
                   style="Big.TButton",
                   command=self.action_build).pack(side="left")

        ttk.Label(controls, text="   Examples:").pack(side="left", padx=(12, 4))
        self.example_var = tk.StringVar()
        cmb = ttk.Combobox(controls, textvariable=self.example_var,
                           values=list(EXAMPLES.keys()),
                           state="readonly", width=44)
        cmb.pack(side="left")
        cmb.bind("<<ComboboxSelected>>", self.action_load_example)

        ttk.Button(controls, text="Clear",
                   command=lambda: self.grammar_text.delete("1.0", "end")
                   ).pack(side="right")

        # right: parsed productions
        right = ttk.LabelFrame(frame, text="Augmented grammar", padding=10)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        self.productions_text = scrolledtext.ScrolledText(
            right, height=14, font=("Consolas", 12), state="disabled",
            background="#f8fafc"
        )
        self.productions_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Tab 2: States
    # ------------------------------------------------------------------
    def _build_tab_states(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=" 2. States (Items) ")

        ttk.Label(frame,
                  text="Canonical collection of LR(0) item sets — kernel items "
                       "first, closure items below, and outgoing GOTO transitions.",
                  foreground=self.PALETTE["neutral"]).pack(anchor="w", pady=(0, 6))

        self.states_text = scrolledtext.ScrolledText(
            frame, font=("Consolas", 12), state="disabled",
            background="#f8fafc"
        )
        self.states_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Tab 3: DFA diagram
    # ------------------------------------------------------------------
    def _build_tab_dfa(self):
        frame = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(frame, text=" 3. DFA Diagram ")

        ttk.Label(frame,
                  text="Drag any box to move it.  Use Next/Back to walk; Tour to animate every transition.",
                  foreground=self.PALETTE["neutral"],
                  font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 2))

        # --- Top row: current state, Back, Reset, Zoom, Save ---
        nav_top = ttk.Frame(frame)
        nav_top.pack(fill="x", pady=(0, 1))

        self.dfa_current_lbl = ttk.Label(
            nav_top, text="Current: —",
            font=("Segoe UI", 10, "bold"),
            foreground=self.PALETTE["primary_dark"],
        )
        self.dfa_current_lbl.pack(side="left", padx=(0, 8))

        self.dfa_back_btn = ttk.Button(
            nav_top, text="← Back",
            command=self.action_dfa_back, state="disabled",
        )
        self.dfa_back_btn.pack(side="left", padx=1)

        self.dfa_reset_btn = ttk.Button(
            nav_top, text="⟲ Reset",
            command=self.action_dfa_reset, state="disabled",
        )
        self.dfa_reset_btn.pack(side="left", padx=1)

        # Right side: zoom + save
        ttk.Button(nav_top, text="💾 Save",
                   command=self.action_save_dfa).pack(side="right", padx=(4, 0))
        ttk.Button(nav_top, text="⛶ Fit",
                   command=self.action_dfa_zoom_fit).pack(side="right", padx=1)
        ttk.Button(nav_top, text="−",  width=3,
                   command=self.action_dfa_zoom_out).pack(side="right", padx=1)
        ttk.Button(nav_top, text="+",  width=3,
                   command=self.action_dfa_zoom_in).pack(side="right", padx=1)

        # --- Combined Next + Tour row ---
        # Next-by-symbol buttons on the left, transition tour controls
        # on the right, all on a single line to save vertical space.
        nav_combined = ttk.Frame(frame)
        nav_combined.pack(fill="x", pady=(0, 1))

        ttk.Label(nav_combined, text="Next:",
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        self.dfa_trans_btns_frame = ttk.Frame(nav_combined)
        self.dfa_trans_btns_frame.pack(side="left", padx=(2, 8))

        # Tour controls pinned to the right side
        self.dfa_anim_play_btn = ttk.Button(
            nav_combined, text="▶ Play",
            command=self.action_dfa_anim_play, state="disabled",
        )
        self.dfa_anim_play_btn.pack(side="right", padx=1)
        self.dfa_anim_next_btn = ttk.Button(
            nav_combined, text="⏭", width=3,
            command=self.action_dfa_anim_next, state="disabled",
        )
        self.dfa_anim_next_btn.pack(side="right", padx=1)
        self.dfa_anim_prev_btn = ttk.Button(
            nav_combined, text="⏮", width=3,
            command=self.action_dfa_anim_prev, state="disabled",
        )
        self.dfa_anim_prev_btn.pack(side="right", padx=1)
        self.dfa_anim_start_btn = ttk.Button(
            nav_combined, text="⟳ Tour",
            command=self.action_dfa_anim_start,
        )
        self.dfa_anim_start_btn.pack(side="right", padx=1)

        # --- Path / animation status (combined into one short line) ---
        self.dfa_history_lbl = ttk.Label(
            frame, text="Path:  —",
            foreground=self.PALETTE["neutral"],
            font=("Consolas", 9),
        )
        self.dfa_history_lbl.pack(anchor="w", pady=(1, 0))

        self.dfa_anim_status = ttk.Label(
            frame, text="",
            foreground=self.PALETTE["neutral"],
            font=("Segoe UI", 9),
        )
        self.dfa_anim_status.pack(anchor="w", pady=(0, 2))

        # --- Canvas ---
        self.dfa_fig = Figure(figsize=(13, 8), dpi=100, facecolor="white")
        # Use almost the full figure area — bigger DFA, less white space.
        self.dfa_fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.02)
        self.dfa_ax = self.dfa_fig.add_subplot(111)
        self.dfa_ax.axis("off")
        self.dfa_ax.text(0.5, 0.5, "Build the parser to see the DFA.",
                         transform=self.dfa_ax.transAxes,
                         ha="center", va="center",
                         fontsize=14, color=self.PALETTE["neutral"])
        self.dfa_canvas = FigureCanvasTkAgg(self.dfa_fig, master=frame)
        self.dfa_canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.dfa_canvas, toolbar_frame)
        toolbar.update()

        # Mouse-wheel zoom for convenience
        self.dfa_canvas.get_tk_widget().bind(
            "<MouseWheel>",
            lambda ev: self._zoom_dfa(1.20 if ev.delta > 0 else 1/1.20),
        )
        # Linux scroll wheel
        self.dfa_canvas.get_tk_widget().bind(
            "<Button-4>", lambda ev: self._zoom_dfa(1.20))
        self.dfa_canvas.get_tk_widget().bind(
            "<Button-5>", lambda ev: self._zoom_dfa(1/1.20))

        # Drag-and-drop on state boxes — lets the user manually nudge
        # boxes that overlap or get clipped by zoom.  Uses matplotlib's
        # event system so coordinates are already in data units.
        self.dfa_canvas.mpl_connect("button_press_event",   self._on_dfa_mouse_down)
        self.dfa_canvas.mpl_connect("motion_notify_event",  self._on_dfa_mouse_move)
        self.dfa_canvas.mpl_connect("button_release_event", self._on_dfa_mouse_up)

        # --- State for navigation ---
        self._current_dfa_state = None
        self._dfa_history: list[tuple[int, str]] = []
        self._dfa_pos = None
        self._dfa_graph = None
        self._dfa_edge_labels = None
        self._dfa_accept_states = set()
        self._dfa_box_dims: dict = {}
        # Persistent view-range for the DFA axes — applied on every draw.
        # None = no DFA built yet; otherwise (xmin, xmax) and (ymin, ymax).
        self._dfa_view_xlim: tuple = None
        self._dfa_view_ylim: tuple = None
        # Cumulative zoom factor applied to text font sizes so that
        # text scales with zoom.  1.0 = original size; >1 zoomed in;
        # <1 zoomed out.  Reset to 1.0 by Fit / Reset / Refresh.
        self._dfa_zoom_factor: float = 1.0
        # Transition-animation state (populated by Start tour)
        # Each entry is a (src_state, symbol, dst_state) triple to walk.
        self._dfa_anim_edges: list[tuple[int, str, int]] = []
        self._dfa_anim_idx: int = -1
        self._dfa_anim_playing: bool = False
        self._dfa_anim_after_id = None
        # Drag-state-box state
        self._dfa_drag_node = None               # node being dragged, or None
        self._dfa_drag_offset = (0, 0)           # offset between cursor and box centre

    # ------------------------------------------------------------------
    # Tab 4: Parsing table
    # ------------------------------------------------------------------
    def _build_tab_table(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=" 4. Parsing Table ")

        ttk.Label(frame,
                  text="ACTION columns hold terminals (sN = shift to state N, "
                       "rN = reduce by production N, acc = accept).  "
                       "GOTO columns hold non-terminals.",
                  foreground=self.PALETTE["neutral"]).pack(anchor="w", pady=(0, 6))

        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)

        self.table_tree = ttk.Treeview(tree_frame, show="headings")
        v = ttk.Scrollbar(tree_frame, orient="vertical",
                          command=self.table_tree.yview)
        h = ttk.Scrollbar(tree_frame, orient="horizontal",
                          command=self.table_tree.xview)
        self.table_tree.configure(yscrollcommand=v.set, xscrollcommand=h.set)
        self.table_tree.grid(row=0, column=0, sticky="nsew")
        v.grid(row=0, column=1, sticky="ns")
        h.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # tag for conflict cells (whole row gets highlighted; cell-level highlight
        # is awkward in Treeview, so we tag rows that contain any conflict)
        self.table_tree.tag_configure("conflict",
                                      background="#fee2e2",
                                      foreground=self.PALETTE["danger"])

        self.conflicts_label = ttk.Label(frame, text="",
                                         foreground=self.PALETTE["danger"],
                                         wraplength=1100,
                                         justify="left")
        self.conflicts_label.pack(fill="x", pady=(8, 0))

    # ------------------------------------------------------------------
    # Tab 5: Parser
    # ------------------------------------------------------------------
    def _build_tab_parser(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=" 5. Parse Input ")

        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(0, 6))

        ttk.Label(bar, text="Input string:").pack(side="left")
        self.input_var = tk.StringVar(value="c c d d")
        ttk.Entry(bar, textvariable=self.input_var, font=("Consolas", 12),
                  width=42).pack(side="left", padx=6)
        ttk.Button(bar, text="▶ Parse all", command=self.action_parse_all
                   ).pack(side="left", padx=2)
        ttk.Button(bar, text="⏮ Reset / Load",
                   command=self.action_reset_steps).pack(side="left", padx=2)
        ttk.Button(bar, text="⏭ Next step",
                   command=self.action_next_step).pack(side="left", padx=2)

        ttk.Label(bar, text="(separate tokens with spaces, "
                            "or just type single-char tokens)",
                  foreground=self.PALETTE["neutral"]).pack(side="left", padx=8)

        self.result_var = tk.StringVar(value="")
        self.result_label = ttk.Label(frame, textvariable=self.result_var,
                                      font=("Segoe UI", 12, "bold"))
        self.result_label.pack(anchor="w", pady=4)

        cols = ("step", "stack", "symbols", "input", "action")
        self.trace_tree = ttk.Treeview(frame, columns=cols,
                                       show="headings", height=20)
        widths = {"step": 60, "stack": 240, "symbols": 240,
                  "input": 240, "action": 360}
        headings = {"step": "Step", "stack": "State stack",
                    "symbols": "Symbol stack",
                    "input": "Input remaining", "action": "Action"}
        for c in cols:
            self.trace_tree.heading(c, text=headings[c])
            self.trace_tree.column(c, width=widths[c], anchor="w")

        self.trace_tree.tag_configure("shift", background="#eff6ff")
        self.trace_tree.tag_configure("reduce", background="#f0fdf4")
        self.trace_tree.tag_configure("accept", background="#bbf7d0",
                                      font=("Consolas", 10, "bold"))
        self.trace_tree.tag_configure("error", background="#fee2e2")

        v = ttk.Scrollbar(frame, orient="vertical",
                          command=self.trace_tree.yview)
        self.trace_tree.configure(yscrollcommand=v.set)
        self.trace_tree.pack(side="left", fill="both", expand=True)
        v.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Tab 6: Parse tree
    # ------------------------------------------------------------------
    def _build_tab_tree(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=" 6. Parse Tree ")

        ttk.Label(frame,
                  text="The derivation tree built by the reductions of the "
                       "last successful parse.",
                  foreground=self.PALETTE["neutral"]).pack(anchor="w", pady=(0, 6))

        self.tree_fig = Figure(figsize=(11, 6.5), dpi=100, facecolor="white")
        self.tree_ax = self.tree_fig.add_subplot(111)
        self.tree_ax.axis("off")
        self.tree_ax.text(0.5, 0.5, "Run a successful parse to see the tree.",
                          transform=self.tree_ax.transAxes,
                          ha="center", va="center",
                          fontsize=14, color=self.PALETTE["neutral"])
        self.tree_canvas = FigureCanvasTkAgg(self.tree_fig, master=frame)
        self.tree_canvas.get_tk_widget().pack(fill="both", expand=True)

    # ==================================================================
    # Actions
    # ==================================================================
    def action_load_example(self, _event=None):
        name = self.example_var.get()
        if name not in EXAMPLES:
            return
        grammar_text, sample_input = EXAMPLES[name]
        self.grammar_text.delete("1.0", "end")
        self.grammar_text.insert("1.0", grammar_text + "\n")
        self.input_var.set(sample_input)

    def action_build(self):
        text = self.grammar_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty grammar",
                                   "Please enter a grammar first.")
            return
        try:
            self.grammar = Grammar.from_text(text)
            self.automaton = LR0Automaton(self.grammar)
            self.table = ParsingTable(self.automaton)
            self.engine = ParserEngine(self.table)
        except Exception as exc:
            messagebox.showerror("Build failed",
                                 f"Could not build the parser:\n\n{exc}")
            self.status_var.set(f"✗  Error: {exc}")
            self._set_banner("error", f"✗  Build failed: {exc}")
            return

        self._refresh_productions()
        self._refresh_states()
        self._refresh_dfa()
        self._refresh_table()
        self._reset_parser_views()

        n_states = len(self.automaton.states)
        n_conflicts = len(self.table.conflicts)

        if n_conflicts == 0:
            self._set_banner(
                "success",
                f"✓  Grammar is LR(0).  Built {n_states} states with no conflicts. "
                f"Ready to parse — switch to the “5. Parse Input” tab to try a string."
            )
            self.status_var.set(
                f"✓  Built parser successfully — {n_states} states, "
                f"grammar IS LR(0)."
            )
        else:
            sr = sum(1 for c in self.table.conflicts if c.kind == "shift/reduce")
            rr = sum(1 for c in self.table.conflicts if c.kind == "reduce/reduce")
            parts = []
            if sr:
                parts.append(f"{sr} shift/reduce")
            if rr:
                parts.append(f"{rr} reduce/reduce")
            self._set_banner(
                "warning",
                f"⚠  This grammar is NOT LR(0).  Found {n_conflicts} conflict(s) "
                f"({', '.join(parts)}) across {n_states} states.  "
                f"The DFA and parsing table are still shown for inspection, but "
                f"some inputs may be rejected.  See the “4. Parsing Table” tab — "
                f"conflict cells are highlighted in red."
            )
            self.status_var.set(
                f"⚠  Built parser — {n_states} states, "
                f"but {n_conflicts} conflict(s): grammar is NOT LR(0)."
            )
            messagebox.showwarning(
                "Grammar is not LR(0)",
                f"This grammar has {n_conflicts} parsing-table conflict(s):\n\n"
                + "\n".join(f"  • State I{c.state} on '{c.symbol}': {c.kind}"
                            for c in self.table.conflicts[:10])
                + ("\n  …" if len(self.table.conflicts) > 10 else "")
                + "\n\nThis means the grammar cannot be parsed deterministically by "
                "an LR(0) parser. The DFA and parsing table are still displayed "
                "so you can inspect the structure."
            )

    def action_save_dfa(self):
        if self.automaton is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
            title="Save DFA diagram",
        )
        if not path:
            return
        self.dfa_fig.savefig(path, bbox_inches="tight", dpi=150)
        self.status_var.set(f"DFA saved to {path}")

    def _check_parsable(self) -> bool:
        """Verify the grammar can actually be parsed; show a helpful message
        and return False if not.  Used by all parse-action handlers."""
        if self.engine is None or self.table is None:
            messagebox.showwarning(
                "No parser",
                "Build the parser first by going to the Grammar tab and "
                "pressing ‘Build Parser’.",
            )
            return False

        # 1) Conflict-based rejection (the grammar isn't LR(0))
        if self.table.conflicts:
            n = len(self.table.conflicts)
            sr = sum(1 for c in self.table.conflicts if c.kind == "shift/reduce")
            rr = sum(1 for c in self.table.conflicts if c.kind == "reduce/reduce")
            parts = []
            if sr:
                parts.append(f"{sr} shift/reduce")
            if rr:
                parts.append(f"{rr} reduce/reduce")
            messagebox.showerror(
                "Grammar is not LR(0) — cannot parse",
                f"This grammar is not LR(0).\n\n"
                f"The parsing table has {n} conflict(s) "
                f"({', '.join(parts)}), so an LR(0) parser cannot "
                f"decide what to do at certain states. The parsing "
                f"trace would be ambiguous, so parsing has been disabled.\n\n"
                f"What you can still do:\n"
                f"  • Inspect the canonical LR(0) item sets in the "
                f"‘2. States (Items)’ tab.\n"
                f"  • Walk the DFA in the ‘3. DFA Diagram’ tab.\n"
                f"  • Check the ‘4. Parsing Table’ tab — conflict cells "
                f"are highlighted in red.\n\n"
                f"To fix the grammar, refactor it to remove the conflicts "
                f"(e.g. by left-factoring, removing ambiguity, or rewriting "
                f"to enforce a precedence/associativity).",
            )
            self.result_var.set(
                "✗  Cannot parse — grammar is not LR(0) "
                f"({n} conflict(s)). See the Parsing Table tab."
            )
            self.result_label.configure(foreground=self.PALETTE["danger"])
            return False

        return True

    def action_parse_all(self):
        if not self._check_parsable():
            return
        accepted, steps, error, tree = self.engine.parse(self.input_var.get())
        self.last_accepted = accepted
        self.last_steps = steps
        self.last_error = error
        self.last_tree = tree
        self.current_step_idx = len(steps)  # all displayed
        self._highlight_dfa_state(None)
        self._fill_trace_table(steps, full=True)
        self._show_result(accepted, error, self.input_var.get())
        self._draw_parse_tree(tree)

    def action_reset_steps(self):
        if not self._check_parsable():
            return
        accepted, steps, error, tree = self.engine.parse(self.input_var.get())
        self.last_accepted = accepted
        self.last_steps = steps
        self.last_error = error
        self.last_tree = tree
        self.current_step_idx = -1
        self.trace_tree.delete(*self.trace_tree.get_children())
        self._highlight_dfa_state(None)
        self.result_var.set(
            f"Loaded {len(steps)} step(s).  Click 'Next step' to advance."
        )
        self.result_label.configure(foreground=self.PALETTE["neutral"])

    def action_next_step(self):
        if not self.last_steps:
            messagebox.showinfo("No trace",
                                "Press '⏮ Reset / Load' first to load a trace.")
            return
        if self.current_step_idx + 1 >= len(self.last_steps):
            # Already at end
            self._show_result(self.last_accepted, self.last_error,
                              self.input_var.get())
            return
        self.current_step_idx += 1
        step = self.last_steps[self.current_step_idx]
        self._append_step_to_trace(step)
        self._highlight_dfa_state(step.current_state)

        # If this was the last step, show the result and tree.
        if self.current_step_idx + 1 == len(self.last_steps):
            self._show_result(self.last_accepted, self.last_error,
                              self.input_var.get())
            self._draw_parse_tree(self.last_tree)

    # ==================================================================
    # View refreshers
    # ==================================================================
    def _refresh_productions(self):
        g = self.grammar
        text = (
            f"Augmented grammar (start symbol: {g.augmented_start}):\n"
            f"{'-' * 50}\n"
        )
        for i, (lhs, rhs) in enumerate(g.productions):
            rhs_str = " ".join(rhs) if rhs else "ε"
            text += f"  ({i})  {lhs} → {rhs_str}\n"
        text += "\n"
        text += f"Non-terminals : {{ {', '.join(sorted(g.non_terminals))} }}\n"
        text += f"Terminals     : {{ {', '.join(sorted(g.terminals))} }}\n"

        self.productions_text.config(state="normal")
        self.productions_text.delete("1.0", "end")
        self.productions_text.insert("1.0", text)
        self.productions_text.config(state="disabled")

    def _refresh_states(self):
        text = (
            f"Canonical collection of LR(0) item sets — "
            f"{len(self.automaton.states)} states:\n"
            + "=" * 64 + "\n\n"
        )
        text += self.automaton.all_states_string()

        self.states_text.config(state="normal")
        self.states_text.delete("1.0", "end")
        self.states_text.insert("1.0", text)
        self.states_text.config(state="disabled")

    # ------------------------------------------------------------------
    # Zoom handlers
    # ------------------------------------------------------------------
    def action_dfa_zoom_in(self):
        self._zoom_dfa(1.25)

    def action_dfa_zoom_out(self):
        self._zoom_dfa(1 / 1.25)

    def action_dfa_zoom_fit(self):
        if self._dfa_graph is None:
            return
        self._fit_dfa_to_layout()
        self._draw_dfa()

    def _zoom_dfa(self, factor):
        """Zoom around the centre of the current view.  Both the visible
        data range AND the text font scale change by `factor`, so text
        and boxes scale together — text never spills outside boxes."""
        if self._dfa_graph is None:
            return
        if self._dfa_view_xlim is None or self._dfa_view_ylim is None:
            return
        x0, x1 = self._dfa_view_xlim
        y0, y1 = self._dfa_view_ylim
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        self._dfa_view_xlim = (cx - rx / factor, cx + rx / factor)
        self._dfa_view_ylim = (cy - ry / factor, cy + ry / factor)
        # Scale font with zoom (clamped to a sensible range)
        self._dfa_zoom_factor = max(0.3, min(4.0,
                                            self._dfa_zoom_factor * factor))
        self._draw_dfa()

    def _fit_dfa_to_layout(self):
        """Reset the view to show the entire layout, with the zoom
        factor adjusted so text scales proportionally to how much the
        view exceeds the axes pixel range.  Text always fits boxes.
        """
        if self._dfa_pos is None or not self._dfa_pos:
            return
        bbox = self.dfa_ax.get_window_extent()
        ax_w_px = max(int(bbox.width),  100)
        ax_h_px = max(int(bbox.height), 100)
        all_x = [p[0] for p in self._dfa_pos.values()]
        all_y = [p[1] for p in self._dfa_pos.values()]
        max_w = max(d[0] for d in self._dfa_box_dims.values())
        max_h = max(d[1] for d in self._dfa_box_dims.values())
        x0 = min(all_x) - max_w / 2 - 30
        x1 = max(all_x) + max_w / 2 + 30
        y0 = min(all_y) - max_h / 2 - 30
        y1 = max(all_y) + max_h / 2 + 40
        view_w = x1 - x0
        view_h = y1 - y0
        zoom = min(ax_w_px / view_w if view_w > ax_w_px else 1.0,
                   ax_h_px / view_h if view_h > ax_h_px else 1.0,
                   1.0)
        x0, x1, y0, y1, zoom = self._apply_min_zoom_floor(
            x0, x1, y0, y1, zoom, ax_w_px, ax_h_px
        )
        self._dfa_view_xlim = (x0, x1)
        self._dfa_view_ylim = (y0, y1)
        self._dfa_zoom_factor = zoom

    def _apply_min_zoom_floor(self, x0, x1, y0, y1, zoom, ax_w_px, ax_h_px):
        """Floor the zoom factor at a readable level (text < 8.5pt is
        hard to read).  When floored, recompute the view range so the
        viewport stays consistent with the zoom level — the layout may
        then exceed the viewport, but the user can pan or drag boxes."""
        MIN_ZOOM = 0.85
        if zoom < MIN_ZOOM:
            zoom = MIN_ZOOM
            target_view_w = ax_w_px / zoom
            target_view_h = ax_h_px / zoom
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            x0 = cx - target_view_w / 2
            x1 = cx + target_view_w / 2
            y0 = cy - target_view_h / 2
            y1 = cy + target_view_h / 2
        return x0, x1, y0, y1, zoom
    # ------------------------------------------------------------------
    def _hit_test_dfa_node(self, x_data, y_data):
        """Return the node id whose box contains (x_data, y_data), or None."""
        if not self._dfa_pos:
            return None
        for n, (cx, cy) in self._dfa_pos.items():
            w, h = self._dfa_box_dims[n]
            if (cx - w / 2 <= x_data <= cx + w / 2 and
                    cy - h / 2 <= y_data <= cy + h / 2):
                return n
        return None

    def _on_dfa_mouse_down(self, event):
        # Only left-click in the axes, with no toolbar mode active
        if event.button != 1 or event.inaxes is not self.dfa_ax:
            return
        # Skip if matplotlib's pan/zoom mode is active (we don't want to
        # fight it for control of the mouse)
        try:
            if self.dfa_canvas.toolbar is not None and \
                    getattr(self.dfa_canvas.toolbar, "mode", ""):
                return
        except Exception:
            pass
        n = self._hit_test_dfa_node(event.xdata, event.ydata)
        if n is None:
            return
        cx, cy = self._dfa_pos[n]
        self._dfa_drag_node = n
        self._dfa_drag_offset = (event.xdata - cx, event.ydata - cy)
        # Visual cue: change cursor to "fleur" (move) while dragging
        try:
            self.dfa_canvas.get_tk_widget().config(cursor="fleur")
        except Exception:
            pass

    def _on_dfa_mouse_move(self, event):
        if self._dfa_drag_node is None or event.inaxes is not self.dfa_ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        ox, oy = self._dfa_drag_offset
        new_x = event.xdata - ox
        new_y = event.ydata - oy
        self._dfa_pos[self._dfa_drag_node] = (new_x, new_y)
        # Redraw with the updated position. The persistent view-range
        # is automatically preserved (we don't touch it here), so the
        # diagram doesn't jerk around as the user drags.
        self._draw_dfa()

    def _on_dfa_mouse_up(self, event):
        if self._dfa_drag_node is None:
            return
        self._dfa_drag_node = None
        try:
            self.dfa_canvas.get_tk_widget().config(cursor="")
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _refresh_dfa(self):
        G = nx.MultiDiGraph()
        edge_labels: dict = {}

        for i in range(len(self.automaton.states)):
            G.add_node(i)
        for src, trans in self.automaton.transitions.items():
            for sym, dst in trans.items():
                if G.has_edge(src, dst):
                    edge_labels[(src, dst)] += f", {sym}"
                else:
                    G.add_edge(src, dst)
                    edge_labels[(src, dst)] = sym

        # Accept states are those containing  S' -> S •
        accept = set()
        for i, st in enumerate(self.automaton.states):
            for it in st:
                if it.prod_idx == 0 and it.is_complete(self.grammar):
                    accept.add(i)

        # We need the canvas live to measure rendered text size.
        # Pin the axes to its pixel range (1:1 data-to-pixel mapping).
        # We KEEP this 1:1 mapping forever — text always renders at
        # the right size relative to box dimensions, so text never
        # overflows boxes regardless of layout extent.
        self.dfa_ax.clear()
        bbox = self.dfa_ax.get_window_extent()
        ax_w_px = max(int(bbox.width),  100)
        ax_h_px = max(int(bbox.height), 100)
        self.dfa_ax.set_xlim(0, ax_w_px)
        self.dfa_ax.set_ylim(0, ax_h_px)
        self.dfa_canvas.draw()

        # Compute box dimensions from worst-case content (in pixels)
        box_dims = self._compute_box_dims()
        # Lay out the boxes (positions in pixel coordinates)
        pos = self._hierarchical_layout_box(G, root=0, box_dims=box_dims)

        # Centre the layout within the axes pixel range.  If the
        # layout is bigger than the axes (large grammars), parts will
        # extend off-screen — the user can drag boxes around or use
        # the matplotlib pan/zoom toolbar to navigate.
        all_x = [p[0] for p in pos.values()]
        all_y = [p[1] for p in pos.values()]
        layout_cx = (min(all_x) + max(all_x)) / 2
        layout_cy = (min(all_y) + max(all_y)) / 2
        target_cx = ax_w_px / 2
        target_cy = ax_h_px / 2 - 25  # leave room for title at top
        dx, dy = target_cx - layout_cx, target_cy - layout_cy
        pos = {n: (x + dx, y + dy) for n, (x, y) in pos.items()}

        self._dfa_graph = G
        self._dfa_edge_labels = edge_labels
        self._dfa_pos = pos
        self._dfa_accept_states = accept
        self._dfa_box_dims = box_dims

        # Initial view = entire layout extent (so user sees everything
        # at first), but with 1:1 data:pixel mapping preserved.
        # If the layout is bigger than the axes, the user will see it
        # zoomed-out, but boxes will still contain their text correctly
        # because text is rendered at fontsize × _dfa_zoom_factor.
        all_x = [p[0] for p in pos.values()]
        all_y = [p[1] for p in pos.values()]
        max_w = max(d[0] for d in box_dims.values())
        max_h = max(d[1] for d in box_dims.values())
        x0 = min(all_x) - max_w / 2 - 30
        x1 = max(all_x) + max_w / 2 + 30
        y0 = min(all_y) - max_h / 2 - 30
        y1 = max(all_y) + max_h / 2 + 40
        # Compute the zoom factor needed to show this range in the axes.
        # If view is wider than axes, zoom < 1 (text shrinks proportionally).
        view_w = x1 - x0
        view_h = y1 - y0
        zoom = min(ax_w_px / view_w if view_w > ax_w_px else 1.0,
                   ax_h_px / view_h if view_h > ax_h_px else 1.0,
                   1.0)
        x0, x1, y0, y1, zoom = self._apply_min_zoom_floor(
            x0, x1, y0, y1, zoom, ax_w_px, ax_h_px
        )
        self._dfa_view_xlim = (x0, x1)
        self._dfa_view_ylim = (y0, y1)
        self._dfa_zoom_factor = zoom

        # Reset navigation to I0
        self._current_dfa_state = 0
        self._dfa_history = []
        self._update_dfa_navigation()
        self._draw_dfa()

    # ------------------------------------------------------------------
    # Navigation handlers
    # ------------------------------------------------------------------
    def action_dfa_back(self):
        if not self._dfa_history:
            return
        prev_state, _ = self._dfa_history.pop()
        self._current_dfa_state = prev_state
        self._clear_trace_if_loaded()
        self._update_dfa_navigation()
        self._draw_dfa()

    def action_dfa_reset(self):
        """Reset navigation to I0, refit the view, and reset zoom.
        (Does not un-drag manually-positioned boxes — those persist
        until the next Build Parser.)"""
        if self._dfa_graph is None:
            return
        self._current_dfa_state = 0
        self._dfa_history = []
        self._clear_trace_if_loaded()
        self._fit_dfa_to_layout()  # also resets _dfa_zoom_factor to 1.0
        self._update_dfa_navigation()
        self._draw_dfa()

    def _dfa_navigate(self, symbol: str):
        cur = self._current_dfa_state
        if cur is None:
            return
        nxt = self.automaton.transitions.get(cur, {}).get(symbol)
        if nxt is None:
            return
        self._dfa_history.append((cur, symbol))
        self._current_dfa_state = nxt
        self._clear_trace_if_loaded()
        self._update_dfa_navigation()
        self._draw_dfa()

    def _clear_trace_if_loaded(self):
        """When the user takes a free-exploration action, stop animation
        so the animation status doesn't get out of sync."""
        if self._dfa_anim_edges:
            self._dfa_anim_edges = []
            self._dfa_anim_idx = -1
            self._dfa_anim_playing = False
            if self._dfa_anim_after_id is not None:
                try:
                    self.root.after_cancel(self._dfa_anim_after_id)
                except Exception:
                    pass
                self._dfa_anim_after_id = None
            self.dfa_anim_prev_btn.config(state="disabled")
            self.dfa_anim_next_btn.config(state="disabled")
            self.dfa_anim_play_btn.config(state="disabled", text="▶ Play")
            self.dfa_anim_status.config(
                text="(animation stopped — switched to free navigation)"
            )

    def _update_dfa_navigation(self):
        cur = self._current_dfa_state
        if cur is None:
            self.dfa_current_lbl.config(text="Current: —")
        else:
            tag = "  (start)" if cur == 0 else ""
            tag += "  (accept)" if cur in self._dfa_accept_states else ""
            self.dfa_current_lbl.config(text=f"Current: I{cur}{tag}")

        self.dfa_back_btn.config(state=("normal" if self._dfa_history else "disabled"))
        self.dfa_reset_btn.config(state=("normal" if cur is not None else "disabled"))

        for w in self.dfa_trans_btns_frame.winfo_children():
            w.destroy()
        if cur is not None:
            trans = self.automaton.transitions.get(cur, {})
            if trans:
                def keyf(s):
                    return (0 if s in self.grammar.terminals else 1, s)
                for sym in sorted(trans.keys(), key=keyf):
                    dest = trans[sym]
                    sym_disp = sym if sym else "ε"
                    ttk.Button(
                        self.dfa_trans_btns_frame,
                        text=f"  {sym_disp}  →  I{dest}  ",
                        command=lambda s=sym: self._dfa_navigate(s),
                    ).pack(side="left", padx=2)
            else:
                ttk.Label(
                    self.dfa_trans_btns_frame,
                    text="(no outgoing transitions — this is a final/reduce state)",
                    foreground=self.PALETTE["neutral"],
                ).pack(side="left")

        if cur is None:
            path_str = "—"
        elif not self._dfa_history:
            path_str = f"I{cur}"
        else:
            parts = []
            for s, sym in self._dfa_history:
                sym_disp = sym if sym else "ε"
                parts.append(f"I{s} ──{sym_disp}──▶ ")
            parts.append(f"I{cur}")
            path_str = "".join(parts)
        self.dfa_history_lbl.config(text=f"Path:  {path_str}")

    # ------------------------------------------------------------------
    # Transition-tour animation: walks every transition in the DFA in
    # source-state order, lighting up the active edge in red.  This
    # gives a complete visual tour of the DFA's structure with no
    # parse-input dependency — the user sees I0 → I1 (on '('), then
    # I0 → I2 (on 'E'), then I0 → I3 (on 'F'), etc.
    # ------------------------------------------------------------------
    def action_dfa_anim_start(self):
        """Build the list of every transition in the DFA in source-state
        order and prime the animation at the first transition."""
        if self.automaton is None:
            messagebox.showinfo(
                "No automaton",
                "Build the parser first by going to the Grammar tab and "
                "pressing ‘Build Parser’.",
            )
            return

        # Collect every (src, sym, dst) triple. Sort by source state so
        # the tour walks I0's outgoing edges first, then I1's, etc.
        edges = []
        for src in sorted(self.automaton.transitions.keys()):
            trans = self.automaton.transitions[src]
            # Within a state, terminals first then non-terminals
            def keyf(s):
                return (0 if s in self.grammar.terminals else 1, s)
            for sym in sorted(trans.keys(), key=keyf):
                edges.append((src, sym, trans[sym]))

        if not edges:
            messagebox.showinfo(
                "No transitions",
                "This DFA has no transitions to animate (it has only one state).",
            )
            return

        self._dfa_anim_edges = edges
        self._dfa_anim_idx = 0
        self._dfa_anim_playing = False

        # Reset highlight state and jump to the first transition's source
        src, sym, dst = edges[0]
        self._dfa_history = [(src, sym)]
        self._current_dfa_state = dst

        self.dfa_anim_prev_btn.config(state="normal")
        self.dfa_anim_next_btn.config(state="normal")
        self.dfa_anim_play_btn.config(state="normal", text="▶ Play")

        self._render_dfa_anim_status()
        self._update_dfa_navigation()
        self._draw_dfa()

    def action_dfa_anim_next(self):
        if not self._dfa_anim_edges:
            return
        if self._dfa_anim_idx >= len(self._dfa_anim_edges) - 1:
            # End of tour — stop auto-play if running
            self._dfa_anim_playing = False
            self.dfa_anim_play_btn.config(text="▶ Play")
            return
        self._dfa_anim_idx += 1
        self._apply_anim_step()

    def action_dfa_anim_prev(self):
        if not self._dfa_anim_edges or self._dfa_anim_idx <= 0:
            return
        self._dfa_anim_idx -= 1
        self._apply_anim_step()

    def action_dfa_anim_play(self):
        """Toggle auto-play.  Advances one transition every 1.2 seconds."""
        if not self._dfa_anim_edges:
            return
        self._dfa_anim_playing = not self._dfa_anim_playing
        if self._dfa_anim_playing:
            self.dfa_anim_play_btn.config(text="⏸ Pause")
            self._dfa_anim_tick()
        else:
            self.dfa_anim_play_btn.config(text="▶ Play")
            if self._dfa_anim_after_id is not None:
                try:
                    self.root.after_cancel(self._dfa_anim_after_id)
                except Exception:
                    pass
                self._dfa_anim_after_id = None

    def _dfa_anim_tick(self):
        if not self._dfa_anim_playing:
            return
        if self._dfa_anim_idx >= len(self._dfa_anim_edges) - 1:
            self._dfa_anim_playing = False
            self.dfa_anim_play_btn.config(text="▶ Play")
            return
        self.action_dfa_anim_next()
        self._dfa_anim_after_id = self.root.after(1200, self._dfa_anim_tick)

    def _apply_anim_step(self):
        """Light up the current transition: its source state is the
        previous highlight, its destination is the new current state,
        and the edge between them is the bright-red active edge."""
        src, sym, dst = self._dfa_anim_edges[self._dfa_anim_idx]
        # Use the existing _dfa_history mechanism: the LAST entry in
        # history is what _draw_dfa renders as the bright red active
        # edge.  We put just this one transition in history so only
        # that arrow lights up.
        self._dfa_history = [(src, sym)]
        self._current_dfa_state = dst
        self._render_dfa_anim_status()
        self._update_dfa_navigation()
        self._draw_dfa()

    def _render_dfa_anim_status(self):
        if not self._dfa_anim_edges:
            return
        i = self._dfa_anim_idx
        n = len(self._dfa_anim_edges)
        src, sym, dst = self._dfa_anim_edges[i]
        sym_disp = sym if sym else "ε"
        self.dfa_anim_status.config(
            text=f"Transition {i + 1} / {n}  •  I{src} ──{sym_disp}──▶ I{dst}"
        )

    # ------------------------------------------------------------------
    # Layout sizing — uses display PIXELS as the working coordinate.
    # Strategy:
    #   1. Measure each state's text in pixels (real rendered size)
    #   2. Lay out states using pixel widths/heights
    #   3. Set the axes xlim/ylim to match the pixel range
    # This guarantees the rendered output exactly matches the layout
    # because everything lives in the same coordinate system from
    # measurement through drawing.
    # ------------------------------------------------------------------
    def _measure_state_texts_px(self):
        """Return {state_idx: (width_px, height_px, lines_count)} based
        on the actual rendered size of each state's combined text.

        We add **generous** padding (30% extra width, 25% extra height
        on top of measurement plus fixed padding) because:
          1) After _fit_dfa_to_layout sets xlim/ylim to a wider range
             than the axes pixel width, data units no longer map 1:1 to
             pixels, so measured-pixel sizes appear shrunken in data
             coords.  Extra room covers the discrepancy.
          2) Edge-label badges sometimes graze the box edge; padding
             prevents them from sitting exactly on the border.
          3) Tk-Agg renderer can produce slightly different metrics
             than the Agg renderer used in headless tests.
        Erring on the "too big" side is fine — small states just have
        a bit of empty space, which actually looks cleaner.
        """
        ax = self.dfa_ax
        fig = self.dfa_fig
        try:
            renderer = fig.canvas.get_renderer()
        except (AttributeError, RuntimeError):
            renderer = None

        FONT_SIZE = 10
        # Inner padding in pixels
        pad_x_px = 22
        pad_y_px = 18
        # Multiplicative slack on top of measured size — generous enough
        # that even when the view-range is wider than the axes width,
        # text still has room inside the box.
        SLACK_W = 1.30
        SLACK_H = 1.20

        sizes = {}
        for n, state in enumerate(self.automaton.states):
            items = sorted(state, key=lambda it: (it.prod_idx, it.dot_pos))
            item_lines = [it.to_string(self.grammar) for it in items]
            header = f"I{n} (start)" if n == 0 else f"I{n}"
            full = "\n".join([header] + item_lines)

            if renderer is not None:
                t = ax.text(0, 0, full, fontsize=FONT_SIZE,
                            family="monospace", ha="center", va="center",
                            alpha=0.0)
                bbox = t.get_window_extent(renderer=renderer)
                t.remove()
                w_px = bbox.width  * SLACK_W + 2 * pad_x_px
                h_px = bbox.height * SLACK_H + 2 * pad_y_px
            else:
                lines = full.split("\n")
                max_chars = max(len(s) for s in lines) if lines else 8
                w_px = max_chars * 7.2 * SLACK_W + 2 * pad_x_px
                h_px = len(lines) * 14   * SLACK_H + 2 * pad_y_px
            sizes[n] = (w_px, h_px)
        return sizes

    def _compute_box_dims(self):
        """Return {state_idx: (width, height)} in DATA units (which are
        pixels because _refresh_dfa pins xlim/ylim to the axes pixel size).

        APPROACH: deterministic char-count formula instead of trying
        to measure rendered text.  Measurement keeps failing because
        after _fit_dfa_to_layout changes xlim/ylim, data units no
        longer map 1:1 to pixels — so a "box that's 92 data-units
        wide" can render narrower than the 92-pixel-wide text inside
        it, causing spillage.

        Fix: compute box dimensions from the longest item string and
        the largest item count *across the entire grammar*.  Every
        box gets the same size.  This wastes a little space for
        small states (1-2 items) but guarantees text always fits.
        """
        # Find the worst case across all states
        max_chars_overall = 12   # floor for header "I_N (start)"
        max_lines_overall = 1    # at least the header line
        for n, state in enumerate(self.automaton.states):
            items = sorted(state, key=lambda it: (it.prod_idx, it.dot_pos))
            item_lines = [it.to_string(self.grammar) for it in items]
            header = f"I{n} (start)" if n == 0 else f"I{n}"
            all_lines = [header] + item_lines
            chars_here = max(len(s) for s in all_lines)
            lines_here = len(all_lines)
            if chars_here > max_chars_overall:
                max_chars_overall = chars_here
            if lines_here > max_lines_overall:
                max_lines_overall = lines_here

        # Fixed-size formula calibrated for fontsize=10 monospace.
        # Real measured per-line height @ 10pt mono is ~16px.
        # Real measured per-char width @ 10pt mono is ~7.2px.
        # We add modest padding for visual comfort.
        CHAR_W   = 8     # px per character (slight slack on 7.2)
        LINE_H   = 18    # px per line (slight slack on 16)
        PAD_X    = 22    # px inner padding left/right
        PAD_Y    = 18    # px inner padding top/bottom

        w = max_chars_overall * CHAR_W + 2 * PAD_X
        h = max_lines_overall * LINE_H + 2 * PAD_Y

        # Every state gets the same size.  This also makes the layout
        # look uniform, which is genuinely cleaner.
        return {n: (w, h) for n in range(len(self.automaton.states))}

    def _draw_dfa(self):
        """Render the DFA.  State boxes are FancyBboxPatch in DATA coords
        (pixel-scaled); text is placed inside them at fixed font size.
        All text and patches set clip_on=True so content never leaks past
        the axes boundaries.

        ax.clear() implicitly resets xlim/ylim, so we explicitly re-apply
        self._dfa_view_xlim/ylim at the END of every draw — that's the
        single source of truth for the visible window.
        """
        if self._dfa_graph is None:
            return
        G              = self._dfa_graph
        pos            = self._dfa_pos
        edge_labels    = self._dfa_edge_labels
        accept         = self._dfa_accept_states
        box_dims       = self._dfa_box_dims
        current        = self._current_dfa_state

        ax = self.dfa_ax
        ax.clear()
        ax.axis("off")

        from matplotlib.patches import FancyArrowPatch

        # --- Pass 1: state boxes (rectangle + ONE text block inside) ---
        # Render header + items as a single text block. This guarantees
        # the rendered text is exactly what _compute_box_dims measured,
        # so it always fits inside the box.  Use ASCII separator that
        # scales with the longest line.
        for n in G.nodes():
            x, y = pos[n]
            w, h = box_dims[n]

            is_current = (n == current)
            is_accept  = (n in accept)
            if is_current:
                fc, ec, lw = "#fff7ed", "#ea580c", 2.6
                txt_color  = "#7c2d12"
            elif is_accept:
                fc, ec, lw = "#f0fdf4", "#15803d", 2.0
                txt_color  = "#14532d"
            else:
                fc, ec, lw = "#ffffff", "#475569", 1.4
                txt_color  = "#0f172a"

            rect = FancyBboxPatch(
                (x - w / 2, y - h / 2), w, h,
                boxstyle="round,pad=0,rounding_size=8",
                facecolor=fc, edgecolor=ec, linewidth=lw,
                clip_on=True, zorder=2,
            )
            ax.add_patch(rect)

            items = sorted(self.automaton.states[n],
                           key=lambda it: (it.prod_idx, it.dot_pos))
            item_lines = [it.to_string(self.grammar) for it in items]
            header = f"I{n} (start)" if n == 0 else f"I{n}"

            # Put header bold (separately, so it stands out), then items
            # below. Position the header near the top of the box, items
            # centred below, so the visual matches the measurement.
            ax.text(x, y, "\n".join([header] + item_lines),
                    fontsize=10 * self._dfa_zoom_factor, family="monospace",
                    color=txt_color,
                    ha="center", va="center",
                    clip_on=True, zorder=3)

        # --- Pass 2: edges ---
        def clip(start, end, cx, cy, w, h):
            dx, dy = end[0] - start[0], end[1] - start[1]
            if dx == 0 and dy == 0:
                return start
            ts = []
            if dx > 0:
                ts.append(((cx + w / 2) - start[0]) / dx)
            elif dx < 0:
                ts.append(((cx - w / 2) - start[0]) / dx)
            if dy > 0:
                ts.append(((cy + h / 2) - start[1]) / dy)
            elif dy < 0:
                ts.append(((cy - h / 2) - start[1]) / dy)
            ts = [t for t in ts if t > 1e-9]
            if not ts:
                return start
            t = min(ts)
            return (start[0] + t * dx, start[1] + t * dy)

        history_edges_set = {
            (hu, self.automaton.transitions.get(hu, {}).get(hsym))
            for hu, hsym in self._dfa_history
        }
        # The edge most recently traversed (the "active" one) gets an
        # extra-bright treatment so users animating the parse trace can
        # see exactly which transition just fired.
        active_edge = None
        if self._dfa_history:
            last_u, last_sym = self._dfa_history[-1]
            last_v = self.automaton.transitions.get(last_u, {}).get(last_sym)
            if last_v is not None:
                active_edge = (last_u, last_v)

        for u, v in set(G.edges()):
            label = edge_labels.get((u, v), "")
            cu, cv = pos[u], pos[v]

            is_active = (u, v) == active_edge
            in_history = (u, v) in history_edges_set
            if is_active:
                edge_color = "#dc2626"   # bright red — "the parser just took this"
                edge_width = 3.5
            elif in_history:
                edge_color = "#ea580c"   # orange — older trail
                edge_width = 2.4
            else:
                edge_color = "#475569"
                edge_width = 1.3

            if u == v:
                wu, hu = box_dims[u]
                cx, cy = cu
                start = (cx + wu * 0.18, cy + hu / 2)
                end   = (cx - wu * 0.18, cy + hu / 2)
                arrow = FancyArrowPatch(
                    start, end,
                    arrowstyle="->", mutation_scale=14,
                    connectionstyle="arc3,rad=-1.4",
                    color=edge_color, linewidth=edge_width,
                    clip_on=True, zorder=1,
                )
                ax.add_patch(arrow)
                ax.text(cx, cy + hu / 2 + 22, label,
                        fontsize=10 * self._dfa_zoom_factor, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.3",
                                  fc="#fef3c7", ec="#f59e0b", lw=0.8),
                        ha="center", va="center", clip_on=True, zorder=11)
            else:
                wu, hu = box_dims[u]
                wv, hv = box_dims[v]
                start = clip(cu, cv, cu[0], cu[1], wu, hu)
                end   = clip(cv, cu, cv[0], cv[1], wv, hv)
                arrow = FancyArrowPatch(
                    start, end,
                    arrowstyle="->", mutation_scale=14,
                    color=edge_color, linewidth=edge_width,
                    clip_on=True, zorder=1,
                )
                ax.add_patch(arrow)
                dx, dy = end[0] - start[0], end[1] - start[1]
                length = (dx * dx + dy * dy) ** 0.5 or 1.0
                # Perpendicular unit vector (90° CCW rotation of direction)
                px, py = -dy / length, dx / length
                # Pixel-scale label size estimate
                lw_est = 9 * max(2, len(label)) + 18
                lh_est = 24

                def overlap_score(lx, ly):
                    """Total overlap area between this candidate label
                    rectangle and ALL state boxes (including the source
                    and destination of this edge — we don't want to
                    cover any state's items text, even the endpoints'
                    headers).
                    """
                    s = 0.0
                    for nn in G.nodes():
                        bx, by = pos[nn]
                        bw, bh = box_dims[nn]
                        bx0, bx1 = bx - bw / 2 + 2, bx + bw / 2 - 2
                        by0, by1 = by - bh / 2 + 2, by + bh / 2 - 2
                        lx0, lx1 = lx - lw_est / 2, lx + lw_est / 2
                        ly0, ly1 = ly - lh_est / 2, ly + lh_est / 2
                        ox = max(0.0, min(lx1, bx1) - max(lx0, bx0))
                        oy = max(0.0, min(ly1, by1) - max(ly0, by0))
                        s += ox * oy
                    return s

                # Try many candidate positions: along the arrow at
                # various points, with several perpendicular offsets.
                # Larger offsets are tried so labels can land in clear
                # space between boxes.  We pick the one with minimum
                # overlap with any box.
                best, best_score = None, float("inf")
                t_values = (0.50, 0.40, 0.60, 0.30, 0.70, 0.25, 0.75, 0.15, 0.85)
                offset_values = (20, -20, 40, -40, 60, -60, 80, -80)
                for t in t_values:
                    for offset in offset_values:
                        cx0 = start[0] + t * dx
                        cy0 = start[1] + t * dy
                        cand = (cx0 + px * offset, cy0 + py * offset)
                        sc = overlap_score(*cand)
                        if sc < best_score:
                            best_score, best = sc, cand
                            if sc == 0:
                                break
                    if best_score == 0:
                        break
                lx, ly = best
                # Highlight the just-traversed edge label too
                if is_active:
                    label_fc, label_ec, label_fc_text = "#fee2e2", "#dc2626", "#7f1d1d"
                    label_fontsize = 11 * self._dfa_zoom_factor
                else:
                    label_fc, label_ec, label_fc_text = "#fef3c7", "#f59e0b", "#000000"
                    label_fontsize = 10 * self._dfa_zoom_factor
                ax.text(lx, ly, label,
                        fontsize=label_fontsize, fontweight="bold",
                        color=label_fc_text,
                        bbox=dict(boxstyle="round,pad=0.3",
                                  fc=label_fc, ec=label_ec, lw=0.8),
                        ha="center", va="center", clip_on=True, zorder=11)

        # --- Apply the stored view-range every time (ax.clear() resets
        # xlim/ylim so we MUST restore them or content would render
        # off-screen).  Initialise from the layout if we don't have a
        # range yet.
        if self._dfa_view_xlim is None or self._dfa_view_ylim is None:
            self._fit_dfa_to_layout()
        ax.set_xlim(*self._dfa_view_xlim)
        ax.set_ylim(*self._dfa_view_ylim)

        title = f"LR(0) DFA  —  {len(G.nodes())} states"
        if current is not None:
            title += f"  •  currently in I{current}"
        ax.set_title(title, fontsize=13, fontweight="bold",
                     color=self.PALETTE["primary_dark"], pad=12)
        self.dfa_canvas.draw()

    def _highlight_dfa_state(self, state_idx):
        """Used by the parse step-through tab to highlight a state."""
        self._current_dfa_state = state_idx
        self._dfa_history = []
        if self._dfa_graph is not None:
            self._update_dfa_navigation()
            self._draw_dfa()

    # ------------------------------------------------------------------
    @staticmethod
    def _hierarchical_layout_box(G, root, box_dims):
        """BFS-layered layout, **left-to-right**: each BFS level becomes
        a vertical column of boxes; columns are placed left-to-right in
        BFS-discovery order.  This keeps the DFA reading like text flow
        (I0 on the left, then states reachable from it, then states
        reachable from those, etc.) and avoids the cramped vertical
        crowding that the top-down layout produced for wide grammars.
        Within each column, nodes are ordered numerically (smallest
        state-index at the top), so I0→I1→I2→… reads in numerical
        order as you scan left-to-right."""
        levels = {root: 0}
        queue = [root]
        while queue:
            n = queue.pop(0)
            for nbr in G.successors(n):
                if nbr not in levels:
                    levels[nbr] = levels[n] + 1
                    queue.append(nbr)
        max_lvl = max(levels.values(), default=0)
        for n in G.nodes():
            if n not in levels:
                max_lvl += 1
                levels[n] = max_lvl

        by_level = {}
        for n, lvl in levels.items():
            by_level.setdefault(lvl, []).append(n)
        sorted_levels = sorted(by_level.keys())

        # If the graph is a single deep chain (one node per level), wrap
        # it into a grid so it doesn't render as a 1-tall row.
        if len(G.nodes()) > 6 and all(len(by_level[l]) <= 1 for l in sorted_levels):
            import math
            n_total = len(G.nodes())
            rows = max(3, math.ceil(math.sqrt(n_total)))
            new_by_level = {}
            for idx, lvl in enumerate(sorted_levels):
                new_lvl = idx // rows
                new_by_level.setdefault(new_lvl, []).extend(by_level[lvl])
            by_level = new_by_level
            sorted_levels = sorted(by_level.keys())

        # Horizontal centres (left-to-right).  Each level is a column.
        h_gap = 90   # pixels between columns
        x_centres = {}
        cur_x = 0.0
        for i, lvl in enumerate(sorted_levels):
            max_w = max(box_dims[n][0] for n in by_level[lvl])
            if i == 0:
                x_centres[lvl] = cur_x
            else:
                prev_max_w = max(box_dims[n][0] for n in by_level[sorted_levels[i - 1]])
                cur_x += (prev_max_w / 2 + max_w / 2 + h_gap)
                x_centres[lvl] = cur_x

        # Vertical positions (stack each column).  Order numerically so
        # I0 sits above I3 in I0's column, etc.  matplotlib y-axis goes
        # UP, so smaller-index = higher-y = top of the column.
        v_gap = 50   # pixels between rows within a column
        pos = {}
        for lvl in sorted_levels:
            nodes = sorted(by_level[lvl])
            heights = [box_dims[n][1] for n in nodes]
            total_h = sum(heights) + (len(heights) - 1) * v_gap
            # Top of column is at +total_h/2; we'll work downward.
            y = total_h / 2.0
            for n, h in zip(nodes, heights):
                pos[n] = (x_centres[lvl], y - h / 2.0)
                y -= h + v_gap
        return pos

    # ------------------------------------------------------------------
    def _refresh_table(self):
        self.table_tree.delete(*self.table_tree.get_children())

        terminals = sorted(self.grammar.terminals) + ["$"]
        non_terminals = sorted(
            self.grammar.non_terminals - {self.grammar.augmented_start}
        )

        cols = ("state",) + tuple(f"act_{t}" for t in terminals) \
                          + tuple(f"goto_{nt}" for nt in non_terminals)
        self.table_tree["columns"] = cols

        self.table_tree.heading("state", text="State")
        self.table_tree.column("state", width=70, anchor="center")

        for t in terminals:
            self.table_tree.heading(f"act_{t}", text=t)
            self.table_tree.column(f"act_{t}", width=80, anchor="center")
        for nt in non_terminals:
            self.table_tree.heading(f"goto_{nt}", text=nt)
            self.table_tree.column(f"goto_{nt}", width=80, anchor="center")

        # Header rows are tricky in Treeview. We add a synthetic first row
        # with grouping labels (ACTION | GOTO).
        action_span = len(terminals)
        goto_span = len(non_terminals)
        header_row = [""] + ["ACTION"] * action_span + ["GOTO"] * goto_span
        self.table_tree.insert("", "end", values=header_row, tags=("header_row",))
        self.table_tree.tag_configure("header_row",
                                      background="#e0e7ff",
                                      font=("Segoe UI", 10, "bold"))

        for i in range(len(self.automaton.states)):
            row = [f"I{i}"]
            row_has_conflict = False
            for t in terminals:
                cell = self.table.action_cell_str(i, t)
                row.append(cell)
                if "/" in cell:  # multiple actions packed into one cell
                    row_has_conflict = True
            for nt in non_terminals:
                row.append(self.table.goto_cell_str(i, nt))

            tag = ("conflict",) if row_has_conflict else ()
            self.table_tree.insert("", "end", values=row, tags=tag)

        if self.table.conflicts:
            txt = (
                f"⚠ {len(self.table.conflicts)} conflict(s) — grammar is NOT LR(0):\n   "
                + "\n   ".join(str(c) for c in self.table.conflicts[:8])
            )
            if len(self.table.conflicts) > 8:
                txt += f"\n   …and {len(self.table.conflicts) - 8} more."
            self.conflicts_label.config(text=txt,
                                        foreground=self.PALETTE["danger"])
        else:
            self.conflicts_label.config(
                text="✓ No conflicts — grammar IS LR(0).",
                foreground=self.PALETTE["success"]
            )

    # ------------------------------------------------------------------
    def _reset_parser_views(self):
        self.last_steps = []
        self.last_tree = None
        self.current_step_idx = -1
        self.trace_tree.delete(*self.trace_tree.get_children())
        self.result_var.set("")
        self.tree_ax.clear()
        self.tree_ax.axis("off")
        self.tree_ax.text(
            0.5, 0.5, "Run a successful parse to see the tree.",
            transform=self.tree_ax.transAxes, ha="center", va="center",
            fontsize=14, color=self.PALETTE["neutral"]
        )
        self.tree_canvas.draw()

    def _fill_trace_table(self, steps, full=True):
        self.trace_tree.delete(*self.trace_tree.get_children())
        for s in steps:
            self._append_step_to_trace(s)

    def _append_step_to_trace(self, step):
        stack_str = " ".join(str(x) for x in step.state_stack)
        sym_str = " ".join(step.symbol_stack)
        inp_str = " ".join(step.input_remaining)
        action_lower = step.action_text.lower()
        if action_lower.startswith("shift"):
            tag = "shift"
        elif action_lower.startswith("reduce"):
            tag = "reduce"
        elif action_lower.startswith("accept"):
            tag = "accept"
        elif action_lower.startswith("error"):
            tag = "error"
        else:
            tag = ""
        item = self.trace_tree.insert(
            "", "end",
            values=(step.step_no, stack_str, sym_str, inp_str, step.action_text),
            tags=(tag,) if tag else ()
        )
        self.trace_tree.see(item)
        self.trace_tree.selection_set(item)

    def _show_result(self, accepted: bool, error: str | None, input_str: str):
        if accepted:
            self.result_var.set(f"✓  ACCEPTED — '{input_str}' is in the language.")
            self.result_label.configure(foreground=self.PALETTE["success"])
        else:
            err = error or "syntax error"
            self.result_var.set(f"✗  REJECTED — {err}")
            self.result_label.configure(foreground=self.PALETTE["danger"])

    # ------------------------------------------------------------------
    # Parse-tree drawing
    # ------------------------------------------------------------------
    def _draw_parse_tree(self, root: ParseNode | None):
        ax = self.tree_ax
        ax.clear()
        ax.axis("off")
        if root is None:
            ax.text(0.5, 0.5, "No parse tree (parse did not succeed).",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=13, color=self.PALETTE["neutral"])
            self.tree_canvas.draw()
            return

        # First pass: assign x positions to leaves; internal nodes get average of children.
        positions: dict[int, tuple[float, float]] = {}
        leaf_counter = [0]

        def assign(node, depth):
            node_id = id(node)
            if node.is_leaf:
                x = leaf_counter[0]
                leaf_counter[0] += 1
                positions[node_id] = (x, -depth)
                return x
            xs = [assign(c, depth + 1) for c in node.children]
            x = sum(xs) / len(xs)
            positions[node_id] = (x, -depth)
            return x

        assign(root, 0)

        # Draw edges
        def draw_edges(node):
            x1, y1 = positions[id(node)]
            for c in node.children:
                x2, y2 = positions[id(c)]
                ax.plot([x1, x2], [y1, y2], color=self.PALETTE["edge"],
                        linewidth=1.2, zorder=1)
                draw_edges(c)
        draw_edges(root)

        # Draw nodes
        def draw_nodes(node):
            x, y = positions[id(node)]
            color = (self.PALETTE["node_accept"] if node.is_leaf
                     else self.PALETTE["node_default"])
            ax.scatter([x], [y], s=900, c=color,
                       edgecolors=self.PALETTE["node_border"],
                       linewidths=1.6, zorder=2)
            ax.text(x, y, node.label, ha="center", va="center",
                    fontsize=10, fontweight="bold", zorder=3)
            for c in node.children:
                draw_nodes(c)
        draw_nodes(root)

        ax.set_title("Parse tree", fontsize=12, fontweight="bold",
                     color=self.PALETTE["primary_dark"])
        # Add some margins
        all_x = [p[0] for p in positions.values()]
        all_y = [p[1] for p in positions.values()]
        if all_x:
            ax.set_xlim(min(all_x) - 0.8, max(all_x) + 0.8)
        if all_y:
            ax.set_ylim(min(all_y) - 0.6, max(all_y) + 0.6)
        self.tree_fig.tight_layout()
        self.tree_canvas.draw()


# ---------------------------------------------------------------------------
def launch():
    root = tk.Tk()
    app = LR0ParserApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
