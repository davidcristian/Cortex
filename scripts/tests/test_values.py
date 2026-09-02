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
        ('  (\n"a"\n"b"\n)  ', "ab"),  # indentation is the writer's, as it is inside a collection
        ("10.0", values.Digits("10.0")),
        ("  5.0  ", values.Digits("5.0")),
        ("5.0  # the short deadline", values.Digits("5.0")),
        ("0.35", values.Digits("0.35")),
        ("1_000.25", values.Digits("1000.25")),  # separators group digits and decide nothing
        ("-1", -1),  # the sentinel a tier's argv reads as "emit no flag"
        ("  -1  ", -1),
        ("-1  # llama.cpp's own word for unbounded", -1),
        ("-2 * 3", -6),  # the sign belongs to the expression, and a product still reduces under one
        ("False", values.Truth("False")),
        ("True", values.Truth("True")),
        ("False  # an escape hatch that ships open is not one", values.Truth("False")),
    ],
)
def test_parse_value_reduces_every_form(text: str, expected: values.Value) -> None:
    """Every accepted form reduces to a value, so two spellings of one number compare equal.

    Comparing the text instead would report `6 * 1024 * 1024` and `6291456` as different.
    """
    assert values.parse_value(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        '"unterminated',  # a lone opening quote
        '"a" + "b"',  # more than one literal
        r'"a\tb"',  # an escape this reducer does not decode
        "6 + 1024",  # arithmetic beyond a product
        "SOME_OTHER_CONST",  # an alias, not a literal
        "10.",  # a point with no digits behind it
        ".5",  # a point with no digits in front of it
        "1.2.3",  # a version, which is not one number
        "1.0e3",  # an exponent this reducer does not evaluate
        "10.0f64",  # Rust's own type suffix, which no registered site spells
        "-5.0",  # a signed decimal, the sign belonging to the integer form alone
        "+1",  # a leading plus, which no rendered needle would spell back
        "2 * -3",  # a sign on a factor rather than on the expression
        "-",  # a sign with no digits behind it
        "false",  # YAML's casing, which is a spelling at a mention and not a form at a site
        "TRUE",  # nor is any other casing of the word
        "None",  # an absence, which is not one of the two words a boolean has
        "6 * 1.5",  # a decimal factor takes the product out of the integer form
        "cortex_seam.SEAM_TOKEN_HEADER",  # an alias whose dot is not a decimal point
        "",  # an empty right-hand side
        "frozenset()",  # a collection with no members
        'frozenset({"a"}) | OTHER',  # a union, whose other half is not a literal
        "frozenset({1, 2})",  # members that are not strings
        'frozenset({"a", b})',  # one member that is not
        "frozenset({'a'})",  # single quotes, which the string form does not read
        "(1, 2)",  # a parenthesis that opens a tuple on one line, not a run of literals
        "(",  # a run that never closes
        '(\n    "a"\n',  # a run whose closing line the capture never found
        "(\n)",  # a run with no literal in it
        "(  # only a comment\n    # and another\n)",  # a run whose every line is a comment
        '(\n    f"a {b}"\n)',  # an f-string inside the run, which is not a literal
        "(\n    NAME\n)",  # a name inside the run
        "(\n    'a'\n)",  # single quotes inside the run
        '(\n    "a" "b"\n)',  # two literals on one line of the run
        '(\n    "a" +\n    "b"\n)',  # a concatenation operator, which the run does not carry
    ],
)
def test_parse_value_refuses_what_it_cannot_reduce(text: str) -> None:
    """An unrecognized form raises instead of being guessed at.

    A guessed reduction would report two values as equal that were never compared.
    """
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


def test_a_boolean_is_not_the_zero_python_says_it_equals() -> None:
    """The reason the word gets its own type: `bool` IS `int` here, and `False == 0` is true.

    A bare boolean would tie a hatch that ships shut to any site declaring zero, and would sort
    under an ordering that has no business over an answer with two values.
    """
    assert values.parse_value("False") != values.parse_value("0")
    assert values.parse_value("True") != values.parse_value("1")
    assert not isinstance(values.parse_value("False"), int)


def test_a_boolean_is_not_the_string_literal_that_spells_it() -> None:
    """Its own type for `Digits`' other reason too: a quoted `"False"` is a different answer."""
    assert values.parse_value("False") != values.parse_value('"False"')


def test_a_boolean_renders_as_the_word_a_needle_and_a_fault_both_want() -> None:
    """The site's own casing, which is what the written spelling substitutes."""
    assert str(values.parse_value("False")) == "False"
    assert f"{values.parse_value('True')!r}" == "True"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("8.0", "8"),  # the shape this exists for: docker takes `8g` and refuses `8.0g`
        ("8.00", "8"),  # a longer fraction, still zero
        ("12", "12"),  # an integer is already whole
        ("1_024.0", "1024"),  # separators grouped the digits and decide nothing here
    ],
)
def test_a_whole_spelling_drops_a_fraction_that_is_zero(text: str, expected: str) -> None:
    """The second spelling a far side needs, derived from the first rather than typed beside it."""
    assert values.spell(values.parse_value(text), couplings.Spelling.WHOLE) == expected


@pytest.mark.parametrize("text", ["8.0", "8.00", "12", '"8.0"', "False", "-1"])
def test_the_written_spelling_is_the_text_the_site_writes(text: str) -> None:
    """The default spelling changes nothing, whatever the value form: the site's own text."""
    written = values.spell(values.parse_value(text), couplings.Spelling.WRITTEN)
    assert written == text.strip('"')


@pytest.mark.parametrize(("text", "expected"), [("False", "false"), ("True", "true")])
def test_a_lowered_spelling_folds_the_word_the_other_language_writes(
    text: str, expected: str
) -> None:
    """The shape this exists for: a compose default spells `false` where the field says `False`."""
    assert values.spell(values.parse_value(text), couplings.Spelling.LOWERED) == expected


@pytest.mark.parametrize("text", ["8.0", "12", '"False"', 'frozenset({"False"})'])
def test_a_value_that_is_not_a_boolean_has_no_lowered_spelling(text: str) -> None:
    """Fail closed: folding a string would tie two literals differing in case alone."""
    with pytest.raises(values.CrossCheckError, match="needs a boolean"):
        values.spell(values.parse_value(text), couplings.Spelling.LOWERED)


def test_only_the_whole_spelling_is_lossy() -> None:
    """Which spellings owe a faithful reading beside them, sorted once for every member.

    `8` and `8.0` are one whole number and one whole spelling, so a whole one can hide a site
    that dropped its point. `False` and `True` lower to two words, so a lowered one cannot hide
    anything, and the written spelling changes nothing at all.
    """
    assert {spelling for spelling in couplings.Spelling if spelling.lossy} == {
        couplings.Spelling.WHOLE
    }


def test_a_fraction_that_is_not_zero_cannot_be_spelled_whole() -> None:
    """Truncating would tie the far side to a number the site does not declare, so it is a fault.

    `8.5` is a budget docker's size suffix cannot carry, and reporting that is the honest answer:
    a silent `8g` would cap the container half a gigabyte under what the scheduler admits, which
    is the drift the coupling exists to report rather than to introduce.
    """
    with pytest.raises(values.CrossCheckError, match="cannot be spelled whole"):
        values.spell(values.parse_value("8.5"), couplings.Spelling.WHOLE)


@pytest.mark.parametrize("text", ['"eight"', 'frozenset({"8"})', "False"])
def test_a_value_that_is_not_a_number_has_no_whole_spelling(text: str) -> None:
    """Fail closed: a re-spelling is arithmetic-shaped, and text has no fractional part to drop."""
    with pytest.raises(values.CrossCheckError, match="needs a number"):
        values.spell(values.parse_value(text), couplings.Spelling.WHOLE)


SITE = couplings.Site("config.py", "BUDGET")
WHOLE_SPEND = couplings.Mention("stack.yml", "{value}g", spelling=couplings.Spelling.WHOLE)
LOWERED_SPEND = couplings.Mention(
    "stack.yml", "${HATCH:-{value}}", spelling=couplings.Spelling.LOWERED
)


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
def test_a_re_spelling_holds_where_something_keeps_the_written_form(
    constant: couplings.Constant,
) -> None:
    """A second site or a mention rendering the value as written is what catches a dropped point."""
    assert values.spelling_fault(constant) is None


@pytest.mark.parametrize(
    "constant",
    [
        _entry(WHOLE_SPEND),
        _entry(
            WHOLE_SPEND,
            couplings.Mention("stack.yml", "{value}g", spelling=couplings.Spelling.WHOLE),
        ),
        _entry(WHOLE_SPEND, couplings.Mention("stack.yml", "var({name})", name="--budget")),
    ],
)
def test_an_entry_that_only_ever_re_spells_is_refused(constant: couplings.Constant) -> None:
    """`8` and `8.0` render alike whole, so an entry with no written reading goes blind to that."""
    fault = values.spelling_fault(constant)
    assert fault is not None
    assert "nothing holds the spelling the site writes" in fault


def test_a_faithful_re_spelling_needs_no_reading_beside_it() -> None:
    """The rule turns on a distinction being lost, and a case fold loses none.

    An entry whose one mention lowers a boolean holds the whole drift by itself: a site that
    flipped renders the other word, so the needle goes unfound with nothing else registered.
    Refusing it would be the whole-number rule applied where its reason does not reach.
    """
    assert values.spelling_fault(_entry(LOWERED_SPEND)) is None
