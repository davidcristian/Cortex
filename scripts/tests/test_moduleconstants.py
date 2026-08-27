"""Behaviour of the reader answering what a Python module's own top level binds.

Everything here is about syntax and nothing is about model tiers, which is the seam this module
was split on. The two answers that look alike and are not, a value this reader cannot reduce and a
sequence one of whose items it cannot reduce, get a check each: a caller that treated them alike
would report a tier's whole tail as empty rather than as unreadable.
"""

import ast
from pathlib import Path

import pytest

from moduleconstants import ModuleReadError, bound, constants, items, parse, text


def _expression(source: str) -> ast.expr:
    """The one expression ``source`` is, which is what both resolvers take."""
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
    """A half-edited module is the shape this really arrives in, and it must not read as empty."""
    path = tmp_path / "m.py"
    path.write_text("def broken(\n", encoding="utf-8")
    with pytest.raises(ModuleReadError, match="cannot read"):
        parse(path, "m.py")


# ── what one expression reduces to ─────────────────────────────────────────────


def test_a_string_literal_is_itself() -> None:
    assert text(_expression("'--jinja'"), {}) == "--jinja"


def test_a_literal_that_is_not_a_string_is_no_argv_item() -> None:
    """A count is a value a command line renders rather than one it carries."""
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
    """The distinction the caller needs: this is a sequence, and one item of it is unknown."""
    assert items(_expression("('--a', str(x))"), {}, {}) == ("--a", None)


def test_something_that_is_no_sequence_at_all_differs_from_one_holding_an_unreadable_item() -> None:
    """A call is not an empty tail, and a reader conflating them would report one as the other."""
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
    """A subscript and an attribute are assignments this reader has no name to answer under."""
    assert bound(_statement("d['k'] = 'x'")) is None
    assert bound(_statement("o.a: str = 'x'")) is None


def test_an_assignment_spreading_one_value_over_two_names_is_not_read() -> None:
    """`A = B = 'x'` is legal and rare, and guessing which name the reader means is worse."""
    assert bound(_statement("A = B = 'x'")) is None


def test_a_statement_that_binds_nothing_is_not_a_declaration() -> None:
    assert bound(_statement("def f():\n    pass")) is None


# ── the whole module, resolved in the order it is written ──────────────────────


def test_every_top_level_string_comes_back_under_its_own_name() -> None:
    strings, tuples = constants(ast.parse("A = '--a'\nB = '--b'\n"))
    assert strings == {"A": "--a", "B": "--b"}
    assert tuples == {}


def test_a_name_written_below_the_one_it_spends_resolves_to_it() -> None:
    """Source order is what makes this resolvable and is also why no cycle is possible."""
    strings, tuples = constants(ast.parse("COUNT = '0'\nPAIR = ('--budget', COUNT)\n"))
    assert strings == {"COUNT": "0"}
    assert tuples == {"PAIR": ("--budget", "0")}


def test_a_name_spending_one_written_below_it_stays_unreadable() -> None:
    """Python would not resolve it either, so a reader that did would be answering for a module
    the interpreter refuses to import."""
    _, tuples = constants(ast.parse("PAIR = ('--budget', COUNT)\nCOUNT = '0'\n"))
    assert tuples == {"PAIR": ("--budget", None)}


def test_a_binding_that_is_neither_a_string_nor_a_run_of_them_is_simply_absent() -> None:
    """A module is full of these and none of them is a fault; the caller asking for a name that
    is not there is the one who knows whether its absence matters."""
    strings, tuples = constants(ast.parse("N = 512\nF = frozenset({'a'})\nA = '--a'\n"))
    assert strings == {"A": "--a"}
    assert tuples == {}


def test_a_name_bound_inside_a_class_or_a_function_is_not_a_module_constant() -> None:
    """Only the top level is read: a field default is not a name the module spends anywhere."""
    source = "class C:\n    A = '--a'\n\n\ndef f():\n    B = '--b'\n    return B\n"
    assert constants(ast.parse(source)) == ({}, {})
