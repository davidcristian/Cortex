import pytest

from shellstrings import shell_strings


def _texts(text: str, *, just: bool = False) -> list[str]:
    return [found for _, found in shell_strings(text, just=just)]


def test_a_double_quoted_string_is_returned_with_its_first_line() -> None:
    source = 'a=1\necho "one line" >&2\nprintf "%s\n  two lines" x\n'
    assert shell_strings(source, just=False) == [(2, "one line"), (3, "%s\n  two lines")]


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ('echo "got $seed now"', "got {} now"),
        ('echo "got $1 and $* and $# now"', "got {} and {} and {} now"),
        ('echo "in ${wait}s"', "in {}s"),
        ('echo "at ${x:-"a b"} now"', "at {} now"),
        ('echo "at $(git rev-parse --short HEAD) now"', "at {} now"),
        ('echo "sum $(( (a << 2) + 1 )) now"', "sum {} now"),
        ('echo "at `date` now"', "at {} now"),
        ('echo "costs 5$ now"', "costs 5$ now"),
    ],
)
def test_each_expansion_is_one_placeholder(source: str, text: str) -> None:
    assert _texts(source)[-1] == text


def test_a_string_inside_a_command_substitution_is_returned_too() -> None:
    source = 'n="$(printf "%s" "the text" | wc -c)"\n'
    assert sorted(_texts(source)) == ["%s", "the text", "{}"]


def test_escapes_stay_as_written_and_do_not_end_the_string() -> None:
    assert _texts('echo "a \\"quoted\\" \\$HOME and \\`x\\`"') == [
        'a \\"quoted\\" \\$HOME and \\`x\\`'
    ]


@pytest.mark.parametrize(
    "source",
    [
        "echo 'a \"not read\" here'",
        'echo don\\"t',
        '# a "comment" here\n',
        'x=1 # a "comment" here\n',
        "# it's a comment\n",
    ],
)
def test_single_quotes_comments_and_escaped_quotes_hold_no_string(source: str) -> None:
    assert _texts(source) == []


def test_a_hash_inside_a_word_does_not_start_a_comment() -> None:
    assert _texts('x=a#b "one" ${#list} $# "two"') == ["one", "two"]


def test_the_line_count_follows_every_skipped_newline() -> None:
    source = "echo 'a\nb'\necho a\\\nb\nx=$(f\n)\n# c\n\"d\"\n"
    assert shell_strings(source, just=False) == [(8, "d")]


def test_parentheses_inside_a_command_substitution_are_balanced() -> None:
    assert _texts('x=$( (a) ) "after" ) "last"') == ["after", "last"]


def test_just_reads_an_interpolation_as_a_placeholder_and_four_braces_as_two() -> None:
    source = 'echo "draw {{ count }} of {{{{x}} now"'
    assert _texts(source, just=True) == ["draw {} of {{x}} now"]
    assert _texts(source) == ["draw {{ count }} of {{{{x}} now"]


@pytest.mark.parametrize(
    ("source", "texts"),
    [
        ('echo "never closed', ["never closed"]),
        ('echo \'never closed "x"', []),
        ('echo "a {{ never closed', ["a {}"]),
        ('echo "a" \\', ["a"]),
    ],
)
def test_text_that_ends_early_ends_the_string(source: str, texts: list[str]) -> None:
    assert _texts(source, just=True) == texts
