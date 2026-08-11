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
    ],
)
def test_parse_value_reduces_every_form(text: str, expected: str | int | frozenset[str]) -> None:
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
        "1600.0",  # not an integer
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
