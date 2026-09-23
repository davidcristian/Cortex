import pytest

from configstrings import yaml_strings


@pytest.mark.parametrize(
    ("line", "text"),
    [
        ("name: Run the gate", "Run the gate"),
        ("name: Run the gate # a note", "Run the gate"),
        ("name: # a note", ""),
        ("name:", ""),
        ('description: "Seed \\"to\\" use" # a note', 'Seed \\"to\\" use'),
        ("description: 'it''s the gate' # a note", "it's the gate"),
        ("  - name: a list item", "a list item"),
        ("  name: a#b c", "a#b c"),
    ],
)
def test_a_name_or_description_value_is_read_as_written(line: str, text: str) -> None:
    assert yaml_strings(f"on: push\n{line}\n") == [(2, text)]


@pytest.mark.parametrize(
    "line",
    [
        "group: shuffle the gate",
        "entry: just check the gate",
        'test: ["CMD", "a gate"]',
        "# name: a comment",
        "names: a gate",
        "- a gate: here",
    ],
)
def test_other_keys_and_comments_are_not_read(line: str) -> None:
    assert yaml_strings(f"{line}\n") == []


def test_a_run_block_returns_its_shell_strings_at_their_own_lines() -> None:
    source = (
        "steps:\n"
        "  - run: |\n"
        '      echo "one gate"\n'
        "\n"
        "      name: not a key\n"
        '      echo "two $x" >&2\n'
        "    name: after the block\n"
    )
    assert yaml_strings(source) == [
        (3, "one gate"),
        (6, "two {}"),
        (7, "after the block"),
    ]


def test_a_block_may_end_the_file() -> None:
    assert yaml_strings('run: >-\n  echo "a gate"') == [(2, "a gate")]


def test_an_inline_run_value_is_read_as_shell() -> None:
    assert yaml_strings('run: just shuffle "$SEED" \'a b\' # "c d"\n') == [(1, "{}")]


def test_a_block_name_is_read_whole() -> None:
    source = "description: | # a note\n  the first\n  and second\nname: x\n"
    assert yaml_strings(source) == [(2, "  the first\n  and second"), (4, "x")]
