"""
grammar.py
==========
Grammar representation for the LR(0) parser.

A Grammar is parsed from text in the form:
    S -> A A
    A -> a A | b
    # comments are allowed
    # use ε or # for epsilon (empty production)

Whitespace inside an RHS is OPTIONAL when the RHS uses operator punctuation
(non-alphanumeric symbols).  For example, both of these are equivalent:
    E -> E + T | T          (spaced — original style)
    E->E+T|T                (no spaces — also accepted)
For grammars whose alphabet is single letters (e.g. S -> a S b), spaces
ARE required, because  aSb  cannot be disambiguated from a 3-char symbol.

The first non-terminal in the first line becomes the start symbol.
The grammar is automatically augmented with a new start production
    S' -> S
which is required by the LR(0) construction (Dragon Book, sec. 4.6).
"""

import re
from dataclasses import dataclass, field
from typing import List, Set, Tuple


# Tokeniser regex for the "no-spaces" RHS form.
# Matches either:
#   - an identifier  [A-Za-z_][A-Za-z0-9_']*    (e.g.  id, E, S', myVar)
#   - or any single non-whitespace, non-word character (e.g.  +, *, (, ), [, ;, ...)
# This is used ONLY when an alternative has no internal whitespace.
_RHS_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*|[^\s\w]")


@dataclass
class Grammar:
    """A context-free grammar augmented with a single new start production.

    Attributes
    ----------
    productions : list of (lhs, rhs_tuple)
        Production 0 is always the augmented production  S' -> S.
        rhs_tuple is empty for an epsilon production.
    terminals, non_terminals : sets of symbols
    start_symbol : the original start symbol (e.g. 'S')
    augmented_start : the new start symbol (e.g. "S'")

    This is a PURE LR(0) implementation — we do not compute FIRST/FOLLOW
    sets (which are needed only for SLR(1)/LL(1)) and we do not run
    productivity/reachability "useless symbol" analysis (which is a
    separate static analysis, not part of LR(0) construction).  Every
    grammar that parses syntactically is accepted; the LR(0) DFA and
    parsing table are built from it directly.
    """
    productions: List[Tuple[str, Tuple[str, ...]]] = field(default_factory=list)
    terminals: Set[str] = field(default_factory=set)
    non_terminals: Set[str] = field(default_factory=set)
    start_symbol: str = ""
    augmented_start: str = ""

    EPSILON_TOKENS = {"ε", "#", "epsilon", "EPSILON"}

    # ------------------------------------------------------------------
    # RHS tokenisation
    # ------------------------------------------------------------------
    @classmethod
    def _tokenize_rhs_alt(cls, alt: str, known_nts: Set[str]) -> Tuple[str, ...]:
        """Tokenise a single right-hand-side alternative.

        Algorithm (three layers, each handling a different ambiguity):

          1.  Whitespace split.   Whatever the user typed with spaces
              between, we trust.  So  'E + T'  →  ['E', '+', 'T'].

          2.  Punctuation split.   For each whitespace-separated chunk,
              we then split on operator punctuation (anything that is
              not a letter/digit/underscore/apostrophe).   So  'E+T'  →
              ['E', '+', 'T']  and  '(E)C'  →  ['(', 'E', ')', 'C'].

          3.  Non-terminal-aware decomposition.   For each remaining
              all-identifier chunk like 'CC', 'aSb', or 'id', we check
              whether the chunk contains any known non-terminal as a
              substring.  If it does, we decompose it left-to-right by
              longest-match against the known non-terminals, treating
              any run of leftover characters as a single multi-char
              terminal.   So with NTs={S,C}:
                'CC'   →  ['C', 'C']
                'aSb'  →  ['a', 'S', 'b']
                'idC'  →  ['id', 'C']
              and with NTs={E,T,F}:
                'id'   →  ['id']        (no NT inside  →  one terminal)
                'E+T'  →  ['E','+','T']  (already split by step 2)

        This handles single-letter alphabets like  S -> CC | aSb  with
        no spaces, while still preserving multi-character terminals
        like 'id', 'num', 'while', etc. that don't share characters
        with any non-terminal name.
        """
        alt = alt.strip()
        if not alt:
            return ()

        # Step 1 + 2: whitespace split, then regex tokenise each piece
        rough: List[str] = []
        for piece in alt.split():
            matches = _RHS_TOKEN_RE.findall(piece)
            if not matches:
                raise ValueError(f"Could not tokenise RHS alternative: {alt!r}")
            rough.extend(matches)

        # Step 3: for each identifier-like token, apply NT-aware decomposition
        nts_sorted = sorted((nt for nt in known_nts if nt), key=len, reverse=True)
        final: List[str] = []
        for tok in rough:
            # Punctuation tokens pass through unchanged
            if not (tok[0].isalpha() or tok[0] == "_"):
                final.append(tok)
                continue
            # Identifier-like: does it contain any known NT as a substring?
            if not any(nt in tok for nt in nts_sorted):
                # No known NT inside — keep the whole identifier as one
                # symbol (this is what makes 'id' stay as 'id').
                final.append(tok)
                continue
            # Decompose: longest-match NTs left-to-right; runs of
            # non-NT chars become single multi-char terminal tokens.
            final.extend(cls._decompose_with_nts(tok, nts_sorted))
        return tuple(final)

    @staticmethod
    def _decompose_with_nts(s: str, nts_sorted: List[str]) -> List[str]:
        """Walk `s` left-to-right.  At each position, greedily match the
        longest known non-terminal.  When no NT matches, scan forward
        until we hit one (or the end), and emit the intervening run as
        a single terminal token."""
        out: List[str] = []
        i, n = 0, len(s)
        while i < n:
            # Try longest-match against known non-terminals
            matched = None
            for nt in nts_sorted:
                if s.startswith(nt, i):
                    matched = nt
                    break
            if matched is not None:
                out.append(matched)
                i += len(matched)
                continue
            # No NT at position i — accumulate run until next NT or end
            j = i + 1
            while j < n:
                if any(s.startswith(nt, j) for nt in nts_sorted):
                    break
                j += 1
            out.append(s[i:j])
            i = j
        return out

    # ------------------------------------------------------------------
    # Parsing grammar from text
    # ------------------------------------------------------------------
    @classmethod
    def from_text(cls, text: str) -> "Grammar":
        g = cls()

        # ---------- Pass 1: structural parse + collect NT names ----------
        # We parse the structure of each line (LHS, alternatives) WITHOUT
        # tokenising the RHS yet, because tokenising  S -> CC  correctly
        # requires knowing whether 'C' is a non-terminal — which we only
        # learn after seeing the line  C -> ... .  Doing two passes lets
        # us tokenise every RHS with full knowledge of the non-terminal
        # alphabet.
        non_terminals_in_order: List[str] = []
        # Each entry: (lhs, [raw_alt_strs], line_no)
        structural: List[Tuple[str, List[str], int]] = []

        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.split('#', 1)[0].strip()  # strip comments
            if not line:
                continue

            # Accept either '->' or the unicode arrow '→'
            if "->" in line:
                lhs_part, rhs_part = line.split("->", 1)
            elif "→" in line:
                lhs_part, rhs_part = line.split("→", 1)
            else:
                raise ValueError(
                    f"Line {line_no}: production missing '->' (got: {raw_line!r})"
                )

            lhs = lhs_part.strip()
            if not lhs:
                raise ValueError(f"Line {line_no}: empty left-hand side")
            if " " in lhs or "\t" in lhs:
                raise ValueError(
                    f"Line {line_no}: LHS must be a single symbol (got {lhs!r})"
                )

            if lhs not in non_terminals_in_order:
                non_terminals_in_order.append(lhs)

            raw_alts = [alt.strip() for alt in rhs_part.split("|")]
            structural.append((lhs, raw_alts, line_no))

        if not structural:
            raise ValueError("Grammar contains no productions.")

        # ---------- Pass 2: tokenise every alternative ----------
        known_nts: Set[str] = set(non_terminals_in_order)
        raw_productions: List[Tuple[str, Tuple[str, ...]]] = []

        for lhs, raw_alts, line_no in structural:
            for alt in raw_alts:
                # Detect epsilon
                if not alt or alt in cls.EPSILON_TOKENS:
                    rhs_tuple: Tuple[str, ...] = ()
                else:
                    rhs_tuple = cls._tokenize_rhs_alt(alt, known_nts)
                raw_productions.append((lhs, rhs_tuple))

        g.non_terminals = set(non_terminals_in_order)
        g.start_symbol = non_terminals_in_order[0]

        # Anything in the RHS that isn't a non-terminal is a terminal.
        for _, rhs in raw_productions:
            for sym in rhs:
                if sym not in g.non_terminals:
                    g.terminals.add(sym)

        # Augment grammar with S' -> S (use unused name for S')
        aug = g.start_symbol + "'"
        while aug in g.non_terminals:
            aug += "'"
        g.augmented_start = aug
        g.non_terminals.add(aug)

        # Production 0 must be the augmented production.
        g.productions.append((aug, (g.start_symbol,)))
        g.productions.extend(raw_productions)
        return g

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    def production_str(self, idx: int) -> str:
        lhs, rhs = self.productions[idx]
        rhs_str = " ".join(rhs) if rhs else "ε"
        return f"{lhs} → {rhs_str}"

    def __str__(self) -> str:
        return "\n".join(
            f"({i}) {self.production_str(i)}" for i in range(len(self.productions))
        )
