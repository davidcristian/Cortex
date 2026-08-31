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
    path = tmp_path / "m.py"
    path.write_text("def broken(\n", encoding="utf-8")
    with pytest.raises(ModuleReadError, match="cannot read"):
        parse(path, "m.py")


def test_a_string_literal_is_itself() -> None:
    assert text(_expression("'--jinja'"), {}) == "--jinja"


def test_a_literal_that_is_not_a_string_is_no_argv_item() -> None:
    assert text(_expression("8083"), {}) is None


def test_a_name_bound_above_resolves_to_what_it_was_bound_to() -> None:
    assert text(_expression("FLAG"), {"FLAG": "--jinja"}) == "--jinja"


def test_a_name_nothing_bound_is_unreadable_rather_than_its_own_spelling() -> None:
    assert text(_expression("FLAG"), {}) is None


def test_a_value_assembled_while_the_program_runs_is_unreadable() -> None:
    assert text(_expression("str(tier.port)"), {}) is None


def test_a_tuple_of_literals_is_the_run_it_writes() -> None:
    assert items(_expression("('--a', '--b')"), {}, {}) == ("--a", "--b")


def test_a_tuple_resolves_the_names_inside_it() -> None:
    assert items(_expression("('--budget', COUNT)"), {"COUNT": "0"}, {}) == ("--budget", "0")


def test_a_name_bound_to_a_tuple_resolves_to_that_tuple() -> None:
    assert items(_expression("PAIR"), {}, {"PAIR": ("--a", "--b")}) == ("--a", "--b")


def test_a_tuple_holding_something_unreadable_is_read_and_that_item_is_not() -> None:
    assert items(_expression("('--a', str(x))"), {}, {}) == ("--a", None)


def test_something_that_is_no_sequence_at_all_differs_from_one_holding_an_unreadable_item() -> None:
    assert items(_expression("self.reasoning()"), {}, {}) is None
    assert items(_expression("NOTHING_BOUND_THIS"), {}, {}) is None


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
    assert bound(_statement("d['k'] = 'x'")) is None
    assert bound(_statement("o.a: str = 'x'")) is None


def test_an_assignment_spreading_one_value_over_two_names_is_not_read() -> None:
    assert bound(_statement("A = B = 'x'")) is None


def test_a_statement_that_binds_nothing_is_not_a_declaration() -> None:
    assert bound(_statement("def f():\n    pass")) is None


def test_every_top_level_string_comes_back_under_its_own_name() -> None:
    strings, tuples = constants(ast.parse("A = '--a'\nB = '--b'\n"))
    assert strings == {"A": "--a", "B": "--b"}
    assert tuples == {}


def test_a_name_written_below_the_one_it_spends_resolves_to_it() -> None:
    strings, tuples = constants(ast.parse("COUNT = '0'\nPAIR = ('--budget', COUNT)\n"))
    assert strings == {"COUNT": "0"}
    assert tuples == {"PAIR": ("--budget", "0")}


def test_a_name_spending_one_written_below_it_stays_unreadable() -> None:
    _, tuples = constants(ast.parse("PAIR = ('--budget', COUNT)\nCOUNT = '0'\n"))
    assert tuples == {"PAIR": ("--budget", None)}


def test_a_binding_that_is_neither_a_string_nor_a_run_of_them_is_simply_absent() -> None:
    strings, tuples = constants(ast.parse("N = 512\nF = frozenset({'a'})\nA = '--a'\n"))
    assert strings == {"A": "--a"}
    assert tuples == {}


def test_a_name_bound_inside_a_class_or_a_function_is_not_a_module_constant() -> None:
    source = "class C:\n    A = '--a'\n\n\ndef f():\n    B = '--b'\n    return B\n"
    assert constants(ast.parse(source)) == ({}, {})
