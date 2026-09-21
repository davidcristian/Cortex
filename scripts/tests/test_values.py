import pytest

import couplings
import values


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("6 * 1024 * 1024", 6291456),
        ("6291456", 6291456),
        ("6_291_456", 6291456),
        ("  6*1024*1024  ", 6291456),
        ("6291456  # the same number, spelled out", 6291456),
        ('"x-cortex-seam-token"', "x-cortex-seam-token"),
        ('"x-cortex-seam-token"  # noqa: S105', "x-cortex-seam-token"),
        ('""', ""),
        ('frozenset({"image/png"})', frozenset({"image/png"})),
        (
            'frozenset({"image/png", "image/jpeg", "image/webp"})',
            frozenset({"image/png", "image/jpeg", "image/webp"}),
        ),
        ('  frozenset({ "image/png" , "image/jpeg" })  ', frozenset({"image/png", "image/jpeg"})),
        ('frozenset({"image/png"})  # what the brain decodes', frozenset({"image/png"})),
        ('(\n    "The refused "\n    "query was "\n)', "The refused query was "),
        ('(\n    "one line"\n)', "one line"),
        (
            '(  # why the run exists\n    "a "  # noqa: E501\n\n    # a note\n    "b"\n)',
            "a b",
        ),
        ('  (\n"a"\n"b"\n)  ', "ab"),
        ("10.0", values.Digits("10.0")),
        ("  5.0  ", values.Digits("5.0")),
        ("5.0  # the short deadline", values.Digits("5.0")),
        ("0.35", values.Digits("0.35")),
        ("1_000.25", values.Digits("1000.25")),
        ("-1", -1),
        ("  -1  ", -1),
        ("-1  # llama.cpp's own word for unbounded", -1),
        ("-2 * 3", -6),
        ("False", values.Truth("False")),
        ("True", values.Truth("True")),
        ("False  # an escape hatch that ships open is not one", values.Truth("False")),
    ],
)
def test_parse_value_reduces_every_form(text: str, expected: values.Value) -> None:
    assert values.parse_value(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        '"unterminated',
        '"a" + "b"',
        r'"a\tb"',
        "6 + 1024",
        "SOME_OTHER_CONST",
        "10.",
        ".5",
        "1.2.3",
        "1.0e3",
        "10.0f64",
        "-5.0",
        "+1",
        "2 * -3",
        "-",
        "false",
        "TRUE",
        "None",
        "6 * 1.5",
        "cortex_seam.SEAM_TOKEN_HEADER",
        "",
        "frozenset()",
        'frozenset({"a"}) | OTHER',
        "frozenset({1, 2})",
        'frozenset({"a", b})',
        "frozenset({'a'})",
        "(1, 2)",
        "(",
        '(\n    "a"\n',
        "(\n)",
        "(  # only a comment\n    # and another\n)",
        '(\n    f"a {b}"\n)',
        "(\n    NAME\n)",
        "(\n    'a'\n)",
        '(\n    "a" "b"\n)',
        '(\n    "a" +\n    "b"\n)',
    ],
)
def test_parse_value_refuses_what_it_cannot_reduce(text: str) -> None:
    with pytest.raises(values.CrossCheckError):
        values.parse_value(text)


def test_a_collection_reduces_to_its_members_rather_than_its_form() -> None:
    one = values.parse_value('frozenset({"image/png", "image/jpeg"})')
    other = values.parse_value('frozenset({ "image/jpeg","image/png" })')
    assert one == other == frozenset({"image/png", "image/jpeg"})


def test_a_decimal_and_the_whole_number_it_equals_are_not_one_value() -> None:
    assert values.parse_value("5.0") != values.parse_value("5")
    assert values.parse_value("5.0") != values.parse_value("5.00")


def test_a_decimal_is_not_the_string_literal_that_writes_it() -> None:
    assert values.parse_value("5.0") != values.parse_value('"5.0"')


def test_a_decimal_renders_as_the_digits_a_search_text_and_a_fault_both_want() -> None:
    assert str(values.parse_value("10.0")) == "10.0"
    assert f"{values.parse_value('10.0')!r}" == "10.0"


def test_a_boolean_is_not_the_zero_python_says_it_equals() -> None:
    assert values.parse_value("False") != values.parse_value("0")
    assert values.parse_value("True") != values.parse_value("1")
    assert not isinstance(values.parse_value("False"), int)


def test_a_boolean_is_not_the_string_literal_that_writes_it() -> None:
    assert values.parse_value("False") != values.parse_value('"False"')


def test_a_boolean_renders_as_the_word_a_search_text_and_a_fault_both_want() -> None:
    assert str(values.parse_value("False")) == "False"
    assert f"{values.parse_value('True')!r}" == "True"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("8.0", "8"),
        ("8.00", "8"),
        ("12", "12"),
        ("1_024.0", "1024"),
    ],
)
def test_a_whole_form_drops_a_fraction_that_is_zero(text: str, expected: str) -> None:
    assert values.in_form(values.parse_value(text), couplings.Form.WHOLE) == expected


@pytest.mark.parametrize("text", ["8.0", "8.00", "12", '"8.0"', "False", "-1"])
def test_the_written_form_is_the_text_the_site_writes(text: str) -> None:
    written = values.in_form(values.parse_value(text), couplings.Form.WRITTEN)
    assert written == text.strip('"')


@pytest.mark.parametrize(("text", "expected"), [("False", "false"), ("True", "true")])
def test_a_lowered_form_folds_the_word_the_other_language_writes(text: str, expected: str) -> None:
    assert values.in_form(values.parse_value(text), couplings.Form.LOWERED) == expected


@pytest.mark.parametrize("text", ["8.0", "12", '"False"', 'frozenset({"False"})'])
def test_a_value_that_is_not_a_boolean_has_no_lowered_form(text: str) -> None:
    with pytest.raises(values.CrossCheckError, match="needs a boolean"):
        values.in_form(values.parse_value(text), couplings.Form.LOWERED)


def test_only_the_whole_form_is_lossy() -> None:
    assert {form for form in couplings.Form if form.lossy} == {couplings.Form.WHOLE}


def test_a_fraction_that_is_not_zero_cannot_be_written_whole() -> None:
    with pytest.raises(values.CrossCheckError, match="cannot be written whole"):
        values.in_form(values.parse_value("8.5"), couplings.Form.WHOLE)


@pytest.mark.parametrize("text", ['"eight"', 'frozenset({"8"})', "False"])
def test_a_value_that_is_not_a_number_has_no_whole_form(text: str) -> None:
    with pytest.raises(values.CrossCheckError, match="needs a number"):
        values.in_form(values.parse_value(text), couplings.Form.WHOLE)


SITE = couplings.Site("config.py", "BUDGET")
WHOLE_SPEND = couplings.Mention("stack.yml", "{value}g", form=couplings.Form.WHOLE)
LOWERED_SPEND = couplings.Mention("stack.yml", "${HATCH:-{value}}", form=couplings.Form.LOWERED)


def _entry(
    *mentions: couplings.Mention, sites: tuple[couplings.Site, ...] = (SITE,)
) -> couplings.Constant:
    return couplings.Constant(
        label="a budget", why="both halves cap one pool", sites=sites, mentions=mentions
    )


@pytest.mark.parametrize(
    "constant",
    [
        _entry(couplings.Mention("stack.yml", "${BUDGET:-{value}}")),
        _entry(WHOLE_SPEND, couplings.Mention("stack.yml", "${BUDGET:-{value}}")),
        _entry(WHOLE_SPEND, sites=(SITE, couplings.Site("body.rs", "BUDGET"))),
    ],
)
def test_a_rewrite_holds_where_something_keeps_the_written_form(
    constant: couplings.Constant,
) -> None:
    assert values.form_fault(constant) is None


@pytest.mark.parametrize(
    "constant",
    [
        _entry(WHOLE_SPEND),
        _entry(
            WHOLE_SPEND,
            couplings.Mention("stack.yml", "{value}g", form=couplings.Form.WHOLE),
        ),
        _entry(WHOLE_SPEND, couplings.Mention("stack.yml", "var({name})", name="--budget")),
    ],
)
def test_an_entry_that_only_ever_rewrites_is_refused(constant: couplings.Constant) -> None:
    fault = values.form_fault(constant)
    assert fault is not None
    assert "nothing holds the form the site writes" in fault


def test_a_faithful_rewrite_needs_no_reading_beside_it() -> None:
    assert values.form_fault(_entry(LOWERED_SPEND)) is None
