"""
parser_engine.py
================
The shift-reduce parsing engine.

Given a parsing table, this module simulates the standard LR parsing
algorithm (Dragon Book, Fig. 4.36) on a tokenised input:

    push 0 onto the stack
    repeat:
        let s = top of stack, a = current input symbol
        case ACTION[s, a] of:
            shift t  -> push a, push t, advance input
            reduce A -> β
                     -> pop 2|β| symbols, let t = top, push A, push GOTO[t, A]
            accept   -> halt successfully
            error    -> halt with error

The engine records every step so the GUI can replay it.
It also builds a parse tree as a side effect of reductions, which
makes it easy to visualise the derivation when parsing succeeds.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from grammar import Grammar
from parsing_table import ParsingTable, ACT_SHIFT, ACT_REDUCE, ACT_ACCEPT


# ---------------------------------------------------------------------------
# Parse trace
# ---------------------------------------------------------------------------
@dataclass
class ParseStep:
    step_no: int
    state_stack: List[int]
    symbol_stack: List[str]
    input_remaining: List[str]
    action_text: str
    # The state we are about to act in (top of stack at the start of the step).
    current_state: int = 0


# ---------------------------------------------------------------------------
# Parse tree
# ---------------------------------------------------------------------------
@dataclass
class ParseNode:
    label: str
    children: List["ParseNode"] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def pretty(self, indent: int = 0) -> str:
        pad = "  " * indent
        if self.is_leaf:
            return f"{pad}{self.label}"
        out = [f"{pad}{self.label}"]
        for c in self.children:
            out.append(c.pretty(indent + 1))
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------
def tokenize(input_str: str, grammar: Grammar) -> List[str]:
    """Tokenise an input string against the grammar's terminal alphabet.

    Strategy (in order):
      1. Whitespace-separated tokens — used if every piece is a known terminal.
      2. Otherwise, longest-match scanning over the (whitespace-removed) string.
    """
    if not input_str.strip():
        return []

    ws_tokens = input_str.split()
    if all(t in grammar.terminals for t in ws_tokens):
        return ws_tokens

    s = "".join(input_str.split())  # remove all whitespace
    tokens: List[str] = []
    i = 0
    # Sort terminals by length descending for longest-match
    longest = max((len(t) for t in grammar.terminals), default=1)
    while i < len(s):
        matched = False
        for length in range(min(longest, len(s) - i), 0, -1):
            candidate = s[i:i + length]
            if candidate in grammar.terminals:
                tokens.append(candidate)
                i += length
                matched = True
                break
        if not matched:
            raise ValueError(
                f"Unknown token at position {i}: {s[i]!r} "
                f"(terminals are {sorted(grammar.terminals)})"
            )
    return tokens


# ---------------------------------------------------------------------------
# Parser engine
# ---------------------------------------------------------------------------
class ParserEngine:
    MAX_STEPS = 5000  # safety net against pathological input

    def __init__(self, table: ParsingTable):
        self.table = table
        self.grammar = table.grammar

    # ------------------------------------------------------------------
    def parse(self, input_str: str) -> Tuple[bool, List[ParseStep], Optional[str], Optional[ParseNode]]:
        """Parse the given input string.

        Returns (accepted, steps, error_message, parse_tree).
        """
        try:
            tokens = tokenize(input_str, self.grammar)
        except ValueError as e:
            err_step = ParseStep(0, [0], [], [str(input_str)], f"Lexical error: {e}", 0)
            return False, [err_step], str(e), None
        tokens.append("$")

        state_stack: List[int] = [0]
        symbol_stack: List[str] = []
        tree_stack: List[ParseNode] = []
        steps: List[ParseStep] = []
        ip = 0
        step_no = 0

        while step_no < self.MAX_STEPS:
            top = state_stack[-1]
            curr = tokens[ip] if ip < len(tokens) else "$"
            action = self.table.action.get((top, curr))

            if action is None:
                steps.append(ParseStep(
                    step_no=step_no,
                    state_stack=list(state_stack),
                    symbol_stack=list(symbol_stack),
                    input_remaining=list(tokens[ip:]),
                    action_text=f"Error: no action for state I{top} on '{curr}'",
                    current_state=top,
                ))
                return False, steps, (
                    f"Syntax error: in state I{top}, "
                    f"the parser saw '{curr}' but the table has no entry."
                ), None

            kind = action[0]

            if kind == ACT_SHIFT:
                steps.append(ParseStep(
                    step_no=step_no,
                    state_stack=list(state_stack),
                    symbol_stack=list(symbol_stack),
                    input_remaining=list(tokens[ip:]),
                    action_text=f"Shift to I{action[1]}",
                    current_state=top,
                ))
                state_stack.append(action[1])
                symbol_stack.append(curr)
                tree_stack.append(ParseNode(curr))  # leaf for the terminal
                ip += 1

            elif kind == ACT_REDUCE:
                prod_idx = action[1]
                lhs, rhs = self.grammar.productions[prod_idx]
                rhs_len = len(rhs)
                steps.append(ParseStep(
                    step_no=step_no,
                    state_stack=list(state_stack),
                    symbol_stack=list(symbol_stack),
                    input_remaining=list(tokens[ip:]),
                    action_text=(
                        f"Reduce by ({prod_idx}) {lhs} → "
                        f"{' '.join(rhs) if rhs else 'ε'}"
                    ),
                    current_state=top,
                ))
                # Pop |β| state-symbol pairs; on ε production, pop nothing.
                if rhs_len > 0:
                    state_stack = state_stack[:-rhs_len]
                    symbol_stack = symbol_stack[:-rhs_len]
                    children = tree_stack[-rhs_len:]
                    tree_stack = tree_stack[:-rhs_len]
                else:
                    children = []
                # Build internal parse-tree node
                tree_stack.append(ParseNode(lhs, list(children)))
                # GOTO
                goto_state = self.table.goto.get((state_stack[-1], lhs))
                if goto_state is None:
                    return False, steps, (
                        f"Missing GOTO entry: GOTO[I{state_stack[-1]}, {lhs}]"
                    ), None
                state_stack.append(goto_state)
                symbol_stack.append(lhs)

            elif kind == ACT_ACCEPT:
                steps.append(ParseStep(
                    step_no=step_no,
                    state_stack=list(state_stack),
                    symbol_stack=list(symbol_stack),
                    input_remaining=list(tokens[ip:]),
                    action_text="Accept",
                    current_state=top,
                ))
                root = tree_stack[-1] if tree_stack else None
                return True, steps, None, root

            else:
                return False, steps, f"Unknown action kind: {kind}", None

            step_no += 1

        return False, steps, "Maximum step count exceeded.", None
