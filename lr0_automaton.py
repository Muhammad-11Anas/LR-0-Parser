"""
lr0_automaton.py
================
Construction of the LR(0) automaton (canonical collection of LR(0) item sets).

Algorithm references the Dragon Book (Aho, Lam, Sethi, Ullman),
sections 4.6.1–4.6.3.

An LR(0) item is a production with a "dot" marking how much of the
right-hand side has been recognised.  For example, for the production

    A -> X Y Z

there are four LR(0) items:

    A -> • X Y Z
    A -> X • Y Z
    A -> X Y • Z
    A -> X Y Z •
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set

from grammar import Grammar


@dataclass(frozen=True)
class LR0Item:
    """A dotted production: (production index, dot position)."""
    prod_idx: int
    dot_pos: int

    def is_complete(self, grammar: Grammar) -> bool:
        _, rhs = grammar.productions[self.prod_idx]
        return self.dot_pos >= len(rhs)

    def next_symbol(self, grammar: Grammar) -> Optional[str]:
        _, rhs = grammar.productions[self.prod_idx]
        if self.dot_pos < len(rhs):
            return rhs[self.dot_pos]
        return None

    def advance(self) -> "LR0Item":
        return LR0Item(self.prod_idx, self.dot_pos + 1)

    def to_string(self, grammar: Grammar) -> str:
        lhs, rhs = grammar.productions[self.prod_idx]
        if not rhs:
            return f"{lhs} → •"
        symbols = list(rhs)
        symbols.insert(self.dot_pos, "•")
        return f"{lhs} → {' '.join(symbols)}"


class LR0Automaton:
    """Builds the canonical collection of LR(0) item sets."""

    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        # states[i] is a frozenset of LR0Item, named I_i
        self.states: List[FrozenSet[LR0Item]] = []
        # transitions[i][symbol] = j  (no entry means no transition)
        self.transitions: Dict[int, Dict[str, int]] = {}
        # The kernel items of each state (useful for textbook-style display)
        self.kernels: List[FrozenSet[LR0Item]] = []
        self._build()

    # ------------------------------------------------------------------
    # Core operations: closure and goto
    # ------------------------------------------------------------------
    def closure(self, items: Set[LR0Item]) -> FrozenSet[LR0Item]:
        """closure(I) — Dragon Book Fig. 4.32.

        For each item [A -> α • B β] in I and each production B -> γ,
        add [B -> • γ] until no more items can be added.
        """
        result: Set[LR0Item] = set(items)
        worklist: List[LR0Item] = list(items)
        while worklist:
            item = worklist.pop()
            sym = item.next_symbol(self.grammar)
            if sym is not None and sym in self.grammar.non_terminals:
                for i, (lhs, _) in enumerate(self.grammar.productions):
                    if lhs == sym:
                        new_item = LR0Item(i, 0)
                        if new_item not in result:
                            result.add(new_item)
                            worklist.append(new_item)
        return frozenset(result)

    def goto(self, items: FrozenSet[LR0Item], symbol: str) -> FrozenSet[LR0Item]:
        """goto(I, X) — Dragon Book Fig. 4.32."""
        moved: Set[LR0Item] = set()
        for item in items:
            if item.next_symbol(self.grammar) == symbol:
                moved.add(item.advance())
        if not moved:
            return frozenset()
        return self.closure(moved)

    # ------------------------------------------------------------------
    # Building the canonical collection
    # ------------------------------------------------------------------
    def _build(self) -> None:
        # I0 = closure({S' -> • S})
        initial_kernel: Set[LR0Item] = {LR0Item(0, 0)}
        initial = self.closure(initial_kernel)

        self.states.append(initial)
        self.kernels.append(frozenset(initial_kernel))
        seen: Dict[FrozenSet[LR0Item], int] = {initial: 0}

        worklist = [0]
        while worklist:
            i = worklist.pop(0)
            state = self.states[i]

            # All grammar symbols that appear right after a dot in this state
            symbols_after_dot: Set[str] = set()
            for item in state:
                sym = item.next_symbol(self.grammar)
                if sym is not None:
                    symbols_after_dot.add(sym)

            # Sort to make construction deterministic
            for sym in sorted(symbols_after_dot):
                # Compute the new state's kernel for storage
                new_kernel: Set[LR0Item] = {
                    item.advance() for item in state
                    if item.next_symbol(self.grammar) == sym
                }
                new_state = self.closure(new_kernel)
                if not new_state:
                    continue

                if new_state in seen:
                    j = seen[new_state]
                else:
                    j = len(self.states)
                    self.states.append(new_state)
                    self.kernels.append(frozenset(new_kernel))
                    seen[new_state] = j
                    worklist.append(j)

                self.transitions.setdefault(i, {})[sym] = j

    # ------------------------------------------------------------------
    # Pretty-printing helpers
    # ------------------------------------------------------------------
    def state_to_string(self, state_idx: int) -> str:
        """Textbook-style display of a state.

        Kernel items first, then closure items, in production-index order.
        """
        kernel = self.kernels[state_idx]
        lines = [f"I{state_idx}:"]
        kernel_sorted = sorted(kernel, key=lambda it: (it.prod_idx, it.dot_pos))
        non_kernel = sorted(
            (it for it in self.states[state_idx] if it not in kernel),
            key=lambda it: (it.prod_idx, it.dot_pos),
        )
        for item in kernel_sorted:
            lines.append(f"    {item.to_string(self.grammar)}")
        if non_kernel:
            for item in non_kernel:
                lines.append(f"    {item.to_string(self.grammar)}")
        return "\n".join(lines)

    def all_states_string(self) -> str:
        out = []
        for i in range(len(self.states)):
            out.append(self.state_to_string(i))
            trans = self.transitions.get(i, {})
            if trans:
                trans_str = ",  ".join(
                    f"GOTO(I{i}, {s}) = I{j}" for s, j in sorted(trans.items())
                )
                out.append(f"    [{trans_str}]")
            out.append("")
        return "\n".join(out)
