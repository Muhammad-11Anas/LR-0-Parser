"""
tests.py
========
Unit tests for the LR(0) parser core (no GUI required).

Run from the project root with:

    python -m unittest tests.py
"""

import unittest

from grammar import Grammar
from lr0_automaton import LR0Automaton, LR0Item
from parsing_table import ParsingTable
from parser_engine import ParserEngine


# ---------------------------------------------------------------------------
class TestGrammar(unittest.TestCase):

    def test_simple_grammar(self):
        g = Grammar.from_text("S -> a S | b")
        self.assertEqual(g.start_symbol, "S")
        self.assertEqual(g.augmented_start, "S'")
        # 1 augmented + 2 user productions
        self.assertEqual(len(g.productions), 3)
        self.assertEqual(g.productions[0], ("S'", ("S",)))
        self.assertEqual(g.terminals, {"a", "b"})

    def test_epsilon_production(self):
        g = Grammar.from_text("S -> A b\nA -> a A | ε")
        # find the epsilon production for A
        eps_prods = [p for p in g.productions if p[0] == "A" and p[1] == ()]
        self.assertEqual(len(eps_prods), 1)

    def test_arrow_unicode_is_accepted(self):
        g = Grammar.from_text("S → a")
        self.assertIn(("S", ("a",)), g.productions)

    def test_missing_arrow_raises(self):
        with self.assertRaises(ValueError):
            Grammar.from_text("S a b")

    def test_no_space_grammar_parses(self):
        """RHS without internal spaces should still tokenise correctly."""
        g = Grammar.from_text("E->E+T|T\nT->T*F|F\nF->(E)|id")
        # Same productions as spaced version
        self.assertIn(("E", ("E", "+", "T")), g.productions)
        self.assertIn(("F", ("(", "E", ")")), g.productions)
        self.assertIn(("F", ("id",)), g.productions)
        self.assertEqual(g.terminals, {"+", "*", "(", ")", "id"})

    def test_no_space_grammar_equals_spaced(self):
        """Spaced and no-space versions must produce identical productions."""
        spaced = Grammar.from_text("E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id")
        no_sp  = Grammar.from_text("E->E+T|T\nT->T*F|F\nF->(E)|id")
        self.assertEqual(spaced.productions, no_sp.productions)
        self.assertEqual(spaced.terminals,   no_sp.terminals)

    def test_mixed_spacing_works(self):
        """A mix of spaced and unspaced alternatives must work."""
        g = Grammar.from_text("E -> E+T | T\nT->T * F|F\nF -> (E)| id")
        self.assertIn(("E", ("E", "+", "T")), g.productions)
        self.assertIn(("T", ("T", "*", "F")), g.productions)
        self.assertIn(("F", ("(", "E", ")")), g.productions)

    def test_single_letter_alphabet_decomposes(self):
        """When non-terminals appear inside an unspaced identifier chunk,
        we now decompose: aSb → [a, S, b] because S is a known NT.
        This is what the user expects for grammars like  S -> CC | aSb ."""
        g = Grammar.from_text("S -> aSb | c")
        self.assertIn(("S", ("a", "S", "b")), g.productions)

    def test_repeated_nt_no_space(self):
        """The user-reported bug: S -> CC must decompose into two C's,
        not a single 2-char symbol 'CC'."""
        g = Grammar.from_text("S->CC\nC->cC|d")
        self.assertIn(("S", ("C", "C")), g.productions)
        # 'C' should be a non-terminal (not a multi-char terminal)
        self.assertIn("C", g.non_terminals)
        self.assertNotIn("CC", g.terminals)

    def test_multichar_terminal_preserved(self):
        """A chunk like 'id' with NTs={E,T,F} contains no known NT,
        so it stays as a single multi-char terminal."""
        g = Grammar.from_text("E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id")
        self.assertIn(("F", ("id",)), g.productions)
        # Make sure 'id' did NOT decompose into 'i' and 'd'
        self.assertNotIn(("F", ("i", "d")), g.productions)
        self.assertIn("id", g.terminals)
        self.assertNotIn("i", g.terminals)
        self.assertNotIn("d", g.terminals)



# ---------------------------------------------------------------------------
class TestAutomatonDragonBook(unittest.TestCase):
    """The example from Dragon Book §4.6 must produce exactly 7 states."""

    def setUp(self):
        self.g = Grammar.from_text("S -> C C\nC -> c C | d")
        self.a = LR0Automaton(self.g)

    def test_state_count(self):
        self.assertEqual(len(self.a.states), 7)

    def test_initial_state(self):
        # I0 must contain S' -> • S  and the closure items
        items_strs = {it.to_string(self.g) for it in self.a.states[0]}
        self.assertIn("S' → • S", items_strs)
        self.assertIn("S → • C C", items_strs)
        self.assertIn("C → • c C", items_strs)
        self.assertIn("C → • d", items_strs)

    def test_no_lr0_conflicts(self):
        t = ParsingTable(self.a)
        self.assertEqual(t.conflicts, [])


# ---------------------------------------------------------------------------
class TestParsing(unittest.TestCase):

    def setUp(self):
        g = Grammar.from_text("S -> C C\nC -> c C | d")
        self.engine = ParserEngine(ParsingTable(LR0Automaton(g)))

    def test_accept(self):
        for s in ["d d", "c d d", "c c d d", "d c d", "c d c d"]:
            with self.subTest(s=s):
                ok, _, err, _ = self.engine.parse(s)
                self.assertTrue(ok, f"Should accept {s!r}, got error: {err}")

    def test_reject(self):
        for s in ["d", "c", "c d", "d d d", "c c d"]:
            with self.subTest(s=s):
                ok, _, _, _ = self.engine.parse(s)
                self.assertFalse(ok, f"Should reject {s!r}")

    def test_parse_tree_structure(self):
        ok, _, _, tree = self.engine.parse("d d")
        self.assertTrue(ok)
        self.assertEqual(tree.label, "S")
        # S -> C C  => root has two children, each labelled C with one leaf 'd'
        self.assertEqual(len(tree.children), 2)
        for child in tree.children:
            self.assertEqual(child.label, "C")
            self.assertEqual(len(child.children), 1)
            self.assertEqual(child.children[0].label, "d")


# ---------------------------------------------------------------------------
class TestConflictDetection(unittest.TestCase):
    """The dangling-else grammar is a canonical non-LR(0) example:

         S -> i S e S | i S | a

       In the state with [S -> i S • e S] and [S -> i S •], pure LR(0)
       puts both a shift on 'e' (from the first item) and a reduce by
       S -> i S (from the second, on every terminal including 'e').
       That's a shift/reduce conflict — the grammar is not LR(0).
    """

    def test_conflict_detected(self):
        g = Grammar.from_text("S -> i S e S | i S | a")
        a = LR0Automaton(g)
        t = ParsingTable(a)
        self.assertGreater(len(t.conflicts), 0,
                           "Expected at least one shift/reduce conflict.")
        kinds = {c.kind for c in t.conflicts}
        self.assertIn("shift/reduce", kinds)


# ---------------------------------------------------------------------------
class TestExpressionGrammar(unittest.TestCase):
    """The classic Dragon Book expression grammar (sec. 4.6.4).

    This grammar is NOT LR(0) — pure LR(0) table construction produces
    shift/reduce conflicts on '*' and '+'.  These are the classic
    conflicts that motivate the SLR(1) and LALR(1) refinements.

    The parser engine still works because it defaults to shift-over-reduce,
    which produces the correct precedence behavior for this grammar.
    """

    def setUp(self):
        self.g = Grammar.from_text(
            "E -> E + T | T\n"
            "T -> T * F | F\n"
            "F -> ( E ) | id"
        )
        self.a = LR0Automaton(self.g)
        self.t = ParsingTable(self.a)
        self.engine = ParserEngine(self.t)

    def test_state_count(self):
        # The canonical state count for this grammar.
        self.assertEqual(len(self.a.states), 12)

    def test_has_lr0_conflicts(self):
        """Pure LR(0) correctly detects that this grammar is NOT LR(0)."""
        self.assertGreater(len(self.t.conflicts), 0)
        # The conflicts are shift/reduce on '*' (and possibly '+')
        kinds = {c.kind for c in self.t.conflicts}
        self.assertIn("shift/reduce", kinds)

    def test_accept_examples(self):
        for s in [
            "id",
            "id + id",
            "id * id",
            "id + id * id",
            "( id )",
            "( id + id ) * id",
            "( ( id ) )",
            "id + id + id * id",
        ]:
            with self.subTest(s=s):
                ok, _, err, _ = self.engine.parse(s)
                self.assertTrue(ok, f"Should accept {s!r}: {err}")

    def test_reject_examples(self):
        for s in ["+ id", "id +", "( id", "id )", "( id + )", "id id"]:
            with self.subTest(s=s):
                ok, _, _, _ = self.engine.parse(s)
                self.assertFalse(ok, f"Should reject {s!r}")


# ---------------------------------------------------------------------------
class TestParenthesesGrammar(unittest.TestCase):

    def setUp(self):
        g = Grammar.from_text("S -> ( S ) | a")
        self.engine = ParserEngine(ParsingTable(LR0Automaton(g)))

    def test_balanced(self):
        for s in ["a", "( a )", "( ( a ) )", "( ( ( a ) ) )"]:
            with self.subTest(s=s):
                ok, _, err, _ = self.engine.parse(s)
                self.assertTrue(ok, f"Should accept {s!r}: {err}")

    def test_unbalanced(self):
        for s in ["( a", "a )", "( ( a )"]:
            with self.subTest(s=s):
                ok, _, _, _ = self.engine.parse(s)
                self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
