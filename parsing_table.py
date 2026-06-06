"""
parsing_table.py
================
Construction of the **pure LR(0)** parsing table.

Algorithm (Dragon Book, §4.5 — LR(0) construction):

For each state I_i:
  1. If [A -> α • a β] is in I_i and goto(I_i, a) = I_j with `a` a terminal,
     then ACTION[i, a] = "shift j".
  2. If [A -> α •] is in I_i (A is not S'), then for EVERY terminal t
     (including $), ACTION[i, t] = "reduce by A -> α".
     This is the key difference from SLR: LR(0) does NOT restrict reduces
     to FOLLOW(A).  Every complete item reduces on every terminal.
  3. If [S' -> S •] is in I_i, then ACTION[i, $] = "accept".
For each non-terminal A:
  4. If goto(I_i, A) = I_j, then GOTO[i, A] = j.

If any cell ends up with more than one entry, the grammar is NOT LR(0) —
it has a shift/reduce or reduce/reduce conflict.  Note that many
"textbook" grammars like the expression grammar (E -> E + T | T) are
NOT LR(0); they require at least SLR(1) to parse without conflicts.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any

from grammar import Grammar
from lr0_automaton import LR0Automaton


# Action types. Stored as small tuples for compactness.
ACT_SHIFT = "shift"
ACT_REDUCE = "reduce"
ACT_ACCEPT = "accept"


def fmt_action(action: Tuple[str, ...]) -> str:
    """Render an action tuple in textbook notation (s5, r3, acc)."""
    if action[0] == ACT_SHIFT:
        return f"s{action[1]}"
    if action[0] == ACT_REDUCE:
        return f"r{action[1]}"
    if action[0] == ACT_ACCEPT:
        return "acc"
    return "?"


@dataclass
class Conflict:
    state: int
    symbol: str
    existing: Tuple[str, ...]
    incoming: Tuple[str, ...]
    kind: str  # 'shift/reduce' or 'reduce/reduce'

    def __str__(self) -> str:
        return (
            f"{self.kind} conflict at state I{self.state} on '{self.symbol}': "
            f"{fmt_action(self.existing)} vs {fmt_action(self.incoming)}"
        )


class ParsingTable:
    """LR(0) parsing table with ACTION and GOTO."""

    def __init__(self, automaton: LR0Automaton):
        self.automaton = automaton
        self.grammar = automaton.grammar

        # ACTION[(state, terminal)] = action tuple
        self.action: Dict[Tuple[int, str], Tuple[str, ...]] = {}
        # GOTO[(state, non_terminal)] = state
        self.goto: Dict[Tuple[int, str], int] = {}
        # Multiple entries per cell when conflicts occur (for display).
        self.action_all: Dict[Tuple[int, str], List[Tuple[str, ...]]] = {}
        self.conflicts: List[Conflict] = []
        self._build()

    # ------------------------------------------------------------------
    def _set_action(self, state: int, terminal: str, new_action: Tuple[str, ...]):
        key = (state, terminal)
        bucket = self.action_all.setdefault(key, [])
        if new_action in bucket:
            return
        if bucket:
            existing = bucket[0]
            kind = (
                "shift/reduce"
                if {existing[0], new_action[0]} == {ACT_SHIFT, ACT_REDUCE}
                else "reduce/reduce"
            )
            self.conflicts.append(
                Conflict(state, terminal, existing, new_action, kind)
            )
        bucket.append(new_action)
        # The "active" action keeps the FIRST one set (shift wins if it came first).
        # In strict LR(0) you don't disambiguate; we just need *some* deterministic
        # choice for the engine to keep moving when the user wants to see the trace.
        if key not in self.action:
            self.action[key] = new_action

    def _build(self) -> None:
        for i, state in enumerate(self.automaton.states):
            # ----- Shifts and GOTOs from transitions
            for sym, j in self.automaton.transitions.get(i, {}).items():
                if sym in self.grammar.terminals:
                    self._set_action(i, sym, (ACT_SHIFT, j))
                else:
                    self.goto[(i, sym)] = j

            # ----- Reductions and accept from complete items
            for item in state:
                if not item.is_complete(self.grammar):
                    continue
                if item.prod_idx == 0:
                    # S' -> S •  ⇒ accept on $
                    self._set_action(i, "$", (ACT_ACCEPT,))
                else:
                    # Pure LR(0): reduce on ALL terminals + $.
                    # This is the textbook LR(0) rule — every complete
                    # item generates a reduce action for every possible
                    # lookahead.  No FOLLOW-set restriction.
                    for t in (self.grammar.terminals | {"$"}):
                        self._set_action(i, t, (ACT_REDUCE, item.prod_idx))

    # ------------------------------------------------------------------
    # Pretty-printing helpers
    # ------------------------------------------------------------------
    def action_cell_str(self, state: int, terminal: str) -> str:
        key = (state, terminal)
        if key not in self.action_all:
            return ""
        # If multiple actions, show them separated by '/'  (visual conflict marker)
        return "/".join(fmt_action(a) for a in self.action_all[key])

    def goto_cell_str(self, state: int, non_terminal: str) -> str:
        v = self.goto.get((state, non_terminal))
        return str(v) if v is not None else ""

    @property
    def is_lr0(self) -> bool:
        return len(self.conflicts) == 0
