"""Tests for the compose substitution reader, form by form.

The reader determines what the defaults gate counts as a spend, so most of the tests below cover
the forms it does not read as one (an escaped dollar, a whole-line comment) and the forms it
raises on rather than guessing. A reader that walks past a real spend leaves the gate unable to
fail, and one that invents a spend fails every later commit.
"""

import pytest

from composedefaults import Substitution, SubstitutionReadError, read_line, read_substitutions


def _one(text: str) -> Substitution:
    """Return the one substitution on a line, asserting the count so a miscount fails here."""
    found = read_line(1, text)
    assert len(found) == 1, found
    return found[0]


# ── the forms compose expands ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("${MODELS_DIR:-./models}", Substitution(1, "MODELS_DIR", ":-", "./models")),
        ("${MODELS_DIR-./models}", Substitution(1, "MODELS_DIR", "-", "./models")),
        ("${TOKEN:+set}", Substitution(1, "TOKEN", ":+", "set")),
        ("${TOKEN+set}", Substitution(1, "TOKEN", "+", "set")),
        ("${USER:?set the username}", Substitution(1, "USER", ":?", "set the username")),
        ("${USER?set the username}", Substitution(1, "USER", "?", "set the username")),
        ("${CA_CERT:-}", Substitution(1, "CA_CERT", ":-", "")),
        ("${MODELS_DIR}", Substitution(1, "MODELS_DIR", "", "")),
    ],
)
def test_every_operator_is_read_as_written(text: str, expected: Substitution) -> None:
    """The operator is kept as written, because `:-` and `-` differ for a variable set to the
    empty string."""
    assert _one(text) == expected


def test_the_bare_posix_form_is_a_spend_too() -> None:
    """`$NAME` is expanded by compose exactly as `${NAME}` is."""
    assert _one("command: $MODELS_DIR/x") == Substitution(1, "MODELS_DIR", "", "")


def test_a_spend_inside_a_quoted_string_is_read() -> None:
    """A substitution inside a quoted YAML value is read, because compose expands before YAML
    parses. The connection string below is the case this covers."""
    line = '      DSN: "postgresql://cortex:${PG_PASSWORD:-cortex}@postgres:5432/cortex"'
    assert _one(line) == Substitution(1, "PG_PASSWORD", ":-", "cortex")


def test_two_spends_on_one_line_are_both_read() -> None:
    """Both substitutions on a line are read, as in the GPU healthcheck, which names two models in
    one shell command."""
    line = "curl /models/${MODEL_CORTEX:-cortex} || curl /models/${MODEL_BRAIN:-brain}"
    assert [spend.name for spend in read_line(9, line)] == ["MODEL_CORTEX", "MODEL_BRAIN"]
    assert [spend.line for spend in read_line(9, line)] == [9, 9]


def test_a_line_with_no_dollar_spends_nothing() -> None:
    assert read_line(1, "    image: cortex-brain") == []


# ── the form that is not a substitution ────────────────────────────────────────


def test_an_escaped_dollar_spends_nothing() -> None:
    """`$$` is compose's literal dollar, and consuming both characters is what keeps `$${V}` as
    text."""
    assert read_line(1, 'test: ["CMD", "echo $$PATH"]') == []
    assert read_line(1, "echo $${MODELS_DIR:-./models}") == []


def test_an_escaped_dollar_does_not_hide_a_later_spend() -> None:
    assert [spend.name for spend in read_line(1, "$$HOME and ${REAL:-x}")] == ["REAL"]


# ── comments ───────────────────────────────────────────────────────────────────


def test_a_whole_line_comment_spends_nothing() -> None:
    """Compose expands nothing in a comment, so a default written there is prose."""
    text = "# defaults to ${MODELS_DIR:-./cache}\n    #   and ${MODELS_DIR:-./other}\n"
    assert read_substitutions(text) == []


def test_a_trailing_comment_is_read_like_any_other_text() -> None:
    """Text after a `#` on a line that has content is read like any other text.

    Recognizing a real comment marker would need a quoting model, and that means tracking block
    scalars too: two of those sit in these compose files carrying a line of odd quotes and content
    compose does interpolate. Reading a spend out of a trailing comment fails loudly and is one
    line from its remedy, while a mistaken marker would drop a real spend from the comparison
    silently.
    """
    spends = read_substitutions('    DIR: "${MODELS_DIR:-./models}"  # or ${MODELS_DIR:-./cache}\n')
    assert [spend.argument for spend in spends] == ["./models", "./cache"]


def test_lines_are_numbered_from_one() -> None:
    text = "services:\n  brain:\n    image: ${IMAGE:-cortex}\n"
    assert read_substitutions(text) == [Substitution(3, "IMAGE", ":-", "cortex")]


# ── everything it will not guess at ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        ("${MODELS_DIR:-./models", "never closes"),
        ("${OUTER:-${INNER}}", "nested substitution"),
        ("${1MODELS:-x}", "names no variable"),
        ("${:-x}", "names no variable"),
        ("${MODELS_DIR:}", "was not taught"),
        ("${MODELS_DIR!x}", "was not taught"),
        ("price: $ 5", "opens no substitution"),
        ('cost: "$"', "opens no substitution"),
    ],
)
def test_a_form_it_was_not_taught_is_raised_not_skipped(text: str, complaint: str) -> None:
    with pytest.raises(SubstitutionReadError, match=complaint):
        read_line(7, text)


def test_a_refusal_names_the_line_it_is_on() -> None:
    with pytest.raises(SubstitutionReadError, match="line 4:"):
        read_substitutions("a:\nb:\nc:\n  d: ${BAD!x}\n")


# ── how a spend describes itself ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("operator", "carries"),
    [
        (":-", True),
        ("-", True),
        (":+", True),
        ("+", True),
        (":?", False),
        ("?", False),
        ("", False),
    ],
)
def test_only_a_fallback_value_is_a_value(operator: str, *, carries: bool) -> None:
    """Only a fallback operator carries a value. A `:?` argument is a message telling whoever runs
    compose what to set, so it is never compared."""
    assert Substitution(1, "V", operator, "x").carries_value is carries


def test_a_spend_writes_itself_back_with_braces() -> None:
    """A fault message shows the spend, and the bare `$V` form is written back with braces so both
    forms read the same way."""
    assert Substitution(1, "V", ":-", "8.0").written == "${V:-8.0}"
    assert Substitution(1, "V", "", "").written == "${V}"
