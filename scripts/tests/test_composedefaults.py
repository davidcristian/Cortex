import pytest

from composedefaults import Substitution, SubstitutionReadError, read_line, read_substitutions


def _one(text: str) -> Substitution:
    """Return the one substitution on a line, asserting the count so a miscount fails here."""
    found = read_line(1, text)
    assert len(found) == 1, found
    return found[0]


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
    assert _one(text) == expected


def test_the_bare_posix_form_is_a_spend_too() -> None:
    assert _one("command: $MODELS_DIR/x") == Substitution(1, "MODELS_DIR", "", "")


def test_a_spend_inside_a_quoted_string_is_read() -> None:
    line = '      DSN: "postgresql://cortex:${PG_PASSWORD:-cortex}@postgres:5432/cortex"'
    assert _one(line) == Substitution(1, "PG_PASSWORD", ":-", "cortex")


def test_two_spends_on_one_line_are_both_read() -> None:
    line = "curl /models/${MODEL_CORTEX:-cortex} || curl /models/${MODEL_BRAIN:-brain}"
    assert [spend.name for spend in read_line(9, line)] == ["MODEL_CORTEX", "MODEL_BRAIN"]
    assert [spend.line for spend in read_line(9, line)] == [9, 9]


def test_a_line_with_no_dollar_spends_nothing() -> None:
    assert read_line(1, "    image: cortex-brain") == []


def test_an_escaped_dollar_spends_nothing() -> None:
    assert read_line(1, 'test: ["CMD", "echo $$PATH"]') == []
    assert read_line(1, "echo $${MODELS_DIR:-./models}") == []


def test_an_escaped_dollar_does_not_hide_a_later_spend() -> None:
    assert [spend.name for spend in read_line(1, "$$HOME and ${REAL:-x}")] == ["REAL"]


def test_a_whole_line_comment_spends_nothing() -> None:
    text = "# defaults to ${MODELS_DIR:-./cache}\n    #   and ${MODELS_DIR:-./other}\n"
    assert read_substitutions(text) == []


def test_a_trailing_comment_is_read_like_any_other_text() -> None:
    spends = read_substitutions('    DIR: "${MODELS_DIR:-./models}"  # or ${MODELS_DIR:-./cache}\n')
    assert [spend.argument for spend in spends] == ["./models", "./cache"]


def test_lines_are_numbered_from_one() -> None:
    text = "services:\n  brain:\n    image: ${IMAGE:-cortex}\n"
    assert read_substitutions(text) == [Substitution(3, "IMAGE", ":-", "cortex")]


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


_NESTED_TAIL = (
    ", whose default is a second spend rather than a value, meaning one thing with nothing "
    "set and another once the inner variable is set"
)


@pytest.mark.parametrize(
    ("text", "fault"),
    [
        ('OUT: "${A:-${B:-x}}tail"', "line 7: nested substitution ${A:-${B:-x}}" + _NESTED_TAIL),
        (
            "${A:-${B:-${C:-deep}}} ${D}",
            "line 7: nested substitution ${A:-${B:-${C:-deep}}}" + _NESTED_TAIL,
        ),
        ('OUT: "${A:-${B}"', "line 7: nested substitution ${A:-${B}" + _NESTED_TAIL),
        (
            'OUT: "${A:-{x}}tail"',
            "line 7: ${A:-{x}} has a brace in its argument, which this reader was not taught",
        ),
        (
            'OUT: "${A:-{x}"',
            "line 7: ${A:-{x} has a brace in its argument, which this reader was not taught",
        ),
    ],
)
def test_a_spend_carrying_a_brace_is_quoted_as_compose_delimits_it(text: str, fault: str) -> None:
    with pytest.raises(SubstitutionReadError) as raised:
        read_line(7, text)
    assert str(raised.value) == fault


def test_a_refusal_names_the_line_it_is_on() -> None:
    with pytest.raises(SubstitutionReadError, match="line 4:"):
        read_substitutions("a:\nb:\nc:\n  d: ${BAD!x}\n")


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
    assert Substitution(1, "V", operator, "x").carries_value is carries


def test_a_spend_writes_itself_back_with_braces() -> None:
    assert Substitution(1, "V", ":-", "8.0").written == "${V:-8.0}"
    assert Substitution(1, "V", "", "").written == "${V}"
