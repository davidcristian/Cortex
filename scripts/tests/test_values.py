import pytest

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
        ("10.0", values.Digits("10.0")),
        ("  5.0  ", values.Digits("5.0")),
        ("5.0  # the short deadline", values.Digits("5.0")),
        ("0.35", values.Digits("0.35")),
        ("1_000.25", values.Digits("1000.25")),  # separators group digits and decide nothing
    ],
)
def test_parse_value_reduces_every_form(text: str, expected: values.Value) -> None:
    """The point of reducing rather than comparing text: two spellings of one number tie."""
    assert values.parse_value(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        '"unterminated',  # a lone opening quote
        '"a" + "b"',  # more than one literal
        r'"a\tb"',  # an escape this reducer will not decode
        "6 + 1024",  # arithmetic beyond a product
        "SOME_OTHER_CONST",  # an alias, not a literal
        "10.",  # a point with no digits behind it
        ".5",  # a point with no digits in front of it
        "1.2.3",  # a version, which is not one number
        "1.0e3",  # an exponent this reducer does not evaluate
        "10.0f64",  # Rust's own type suffix, which no registered site spells
        "-5.0",  # a sign, refused as it is on a product of integers
        "6 * 1.5",  # a product a decimal factor takes out of the integer form
        "cortex_seam.SEAM_TOKEN_HEADER",  # an alias whose dot is not a decimal point
        "",  # an empty right-hand side
        "frozenset()",  # a collection with no member to hold anything
        'frozenset({"a"}) | OTHER',  # a union, whose other half is not a literal
        "frozenset({1, 2})",  # members that are not strings
        'frozenset({"a", b})',  # one member that is not
        "frozenset({'a'})",  # single quotes, which the string form does not read
    ],
)
def test_parse_value_refuses_what_it_cannot_reduce(text: str) -> None:
    """Fail closed: a form the reducer does not understand is a fault, never a guess."""
    with pytest.raises(values.CrossCheckError):
        values.parse_value(text)


def test_a_collection_reduces_to_its_members_rather_than_its_spelling() -> None:
    """Order and spacing are the writer's; the set is what a membership is decided against."""
    one = values.parse_value('frozenset({"image/png", "image/jpeg"})')
    other = values.parse_value('frozenset({ "image/jpeg","image/png" })')
    assert one == other == frozenset({"image/png", "image/jpeg"})


def test_a_decimal_and_the_whole_number_it_equals_are_not_one_value() -> None:
    """The decision this form turns on: `5` and `5.0` are one number and two spellings.

    A float reducer would tie them, and the tie would be wrong in the direction that matters: a
    site retyped as `5` would keep agreeing while every mention went looking for `5.0`.
    """
    assert values.parse_value("5.0") != values.parse_value("5")
    assert values.parse_value("5.0") != values.parse_value("5.00")


def test_a_decimal_is_not_the_string_literal_that_spells_it() -> None:
    """Digits of its own type, so a quoted `"5.0"` somewhere is not a reading of this number."""
    assert values.parse_value("5.0") != values.parse_value('"5.0"')


def test_a_decimal_renders_as_the_digits_a_needle_and_a_fault_both_want() -> None:
    """What a mention substitutes into its template, and what a disagreement prints."""
    assert str(values.parse_value("10.0")) == "10.0"
    assert f"{values.parse_value('10.0')!r}" == "10.0"
