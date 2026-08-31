"""Tests for the reader that answers what a Python module's top level binds.

Everything here is about syntax rather than about model tiers, which is the seam this module was
split on. Two answers that look alike get a check each: a value this reader cannot reduce, and a
sequence one of whose items it cannot reduce. A caller that treated them as the same answer would
report a tier's whole argv tail as empty rather than as unreadable.
"""

import ast
from pathlib import Path

import pytest

from moduleconstants import ModuleReadError, bound, constants, items, parse, text


def _expression(source: str) -> ast.expr:
    """Return the single expression in ``source``, which is what both resolvers take."""
    statement = ast.parse(source).body[0]
    assert isinstance(statement, ast.Expr)
    return statement.value


def _statement(source: str) -> ast.stmt:
    return ast.parse(source).body[0]


# ── reading a module at all ────────────────────────────────────────────────────


def test_a_module_that_parses_comes_back_as_one(tmp_path: Path) -> None:
    path = tmp_path / "m.py"
    path.write_text("A = 'x'\n", encoding="utf-8")
    assert [type(node) for node in parse(path, "m.py").body] == [ast.Assign]


def test_a_module_that_is_not_there_is_named_rather_than_guessed_at(tmp_path: Path) -> None:
    with pytest.raises(ModuleReadError, match=r"cannot read shown/as\.py"):
        parse(tmp_path / "gone.py", "shown/as.py")


def test_a_module_that_is_not_text_is_named(tmp_path: Path) -> None:
    path = tmp_path / "m.py"
    path.write_bytes(b"\xff\xfe not text")
    with pytest.raises(ModuleReadError, match="cannot read"):
        parse(path, "m.py")


def test_a_module_that_is_not_python_is_named(tmp_path: Path) -> None:
    """A module that does not parse raises rather than reading as empty. A half-edited file is the
    shape this case arrives in."""
    path = tmp_path / "m.py"
    path.write_text("def broken(\n", encoding="utf-8")
    with pytest.raises(ModuleReadError, match="cannot read"):
        parse(path, "m.py")


# ── what one expression reduces to ─────────────────────────────────────────────


def test_a_string_literal_is_itself() -> None:
    assert text(_expression("'--jinja'"), {}) == "--jinja"


def test_a_literal_that_is_not_a_string_is_no_argv_item() -> None:
    """A number reduces to nothing, because a command line renders a count rather than carrying it
    as a string."""
    assert text(_expression("8083"), {}) is None


def test_a_name_bound_above_resolves_to_what_it_was_bound_to() -> None:
    assert text(_expression("FLAG"), {"FLAG": "--jinja"}) == "--jinja"


def test_a_name_nothing_bound_is_unreadable_rather_than_its_own_spelling() -> None:
    assert text(_expression("FLAG"), {}) is None


def test_a_value_assembled_while_the_program_runs_is_unreadable() -> None:
    assert text(_expression("str(tier.port)"), {}) is None


# ── and what one sequence reduces to ───────────────────────────────────────────


def test_a_tuple_of_literals_is_the_run_it_writes() -> None:
    assert items(_expression("('--a', '--b')"), {}, {}) == ("--a", "--b")


def test_a_tuple_resolves_the_names_inside_it() -> None:
    assert items(_expression("('--budget', COUNT)"), {"COUNT": "0"}, {}) == ("--budget", "0")


def test_a_name_bound_to_a_tuple_resolves_to_that_tuple() -> None:
    assert items(_expression("PAIR"), {}, {"PAIR": ("--a", "--b")}) == ("--a", "--b")


def test_a_tuple_holding_something_unreadable_is_read_and_that_item_is_not() -> None:
    """A sequence is still read when one of its items cannot be reduced, and that item comes back
    as None."""
    assert items(_expression("('--a', str(x))"), {}, {}) == ("--a", None)


def test_something_that_is_no_sequence_at_all_differs_from_one_holding_an_unreadable_item() -> None:
    """An expression that is no sequence at all comes back as None, which is a different answer
    from the sequence above holding an unreadable item. A reader that returned the same value for
    both would report a call as an empty argv tail."""
    assert items(_expression("self.reasoning()"), {}, {}) is None
    assert items(_expression("NOTHING_BOUND_THIS"), {}, {}) is None


# ── what a statement binds ─────────────────────────────────────────────────────


def test_a_plain_assignment_binds_its_name() -> None:
    declared = bound(_statement("A = 'x'"))
    assert declared is not None
    assert declared[0] == "A"


def test_an_annotated_assignment_binds_its_name_which_is_how_a_field_is_written() -> None:
    declared = bound(_statement("a: str = Field(default='')"))
    assert declared is not None
    assert declared[0] == "a"


def test_an_annotation_with_no_value_binds_nothing() -> None:
    assert bound(_statement("a: str")) is None


def test_an_assignment_to_something_other_than_a_bare_name_binds_no_name_here() -> None:
    """A subscript or an attribute target binds no name this reader can answer under."""
    assert bound(_statement("d['k'] = 'x'")) is None
    assert bound(_statement("o.a: str = 'x'")) is None


def test_an_assignment_spreading_one_value_over_two_names_is_not_read() -> None:
    """`A = B = 'x'` binds nothing here. The form is legal and rare, and this reader answers under
    a single name, so reading it would mean picking one of the two."""
    assert bound(_statement("A = B = 'x'")) is None


def test_a_statement_that_binds_nothing_is_not_a_declaration() -> None:
    assert bound(_statement("def f():\n    pass")) is None


# ── the whole module, resolved in the order it is written ──────────────────────


def test_every_top_level_string_comes_back_under_its_own_name() -> None:
    strings, tuples = constants(ast.parse("A = '--a'\nB = '--b'\n"))
    assert strings == {"A": "--a", "B": "--b"}
    assert tuples == {}


def test_a_name_written_below_the_one_it_spends_resolves_to_it() -> None:
    """Names resolve in source order, which is what makes this readable and why no cycle can
    form."""
    strings, tuples = constants(ast.parse("COUNT = '0'\nPAIR = ('--budget', COUNT)\n"))
    assert strings == {"COUNT": "0"}
    assert tuples == {"PAIR": ("--budget", "0")}


def test_a_name_spending_one_written_below_it_stays_unreadable() -> None:
    """A name used above the line that binds it stays unreadable, since Python would not resolve it
    either, and answering would describe a module the interpreter fails to import."""
    _, tuples = constants(ast.parse("PAIR = ('--budget', COUNT)\nCOUNT = '0'\n"))
    assert tuples == {"PAIR": ("--budget", None)}


def test_a_binding_that_is_neither_a_string_nor_a_run_of_them_is_simply_absent() -> None:
    """A binding that is neither a string nor a sequence of strings is left out rather than
    raising. A module is full of them, and the caller asking for a name is the one that knows
    whether its absence matters."""
    strings, tuples = constants(ast.parse("N = 512\nF = frozenset({'a'})\nA = '--a'\n"))
    assert strings == {"A": "--a"}
    assert tuples == {}


def test_a_name_bound_inside_a_class_or_a_function_is_not_a_module_constant() -> None:
    """Only the module's top level is read, since a name bound inside a class body or a function is
    not one another module can spend."""
    source = "class C:\n    A = '--a'\n\n\ndef f():\n    B = '--b'\n    return B\n"
    assert constants(ast.parse(source)) == ({}, {})
