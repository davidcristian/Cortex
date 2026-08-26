"""Behaviour of the reader that answers what a service starts with and what environment it gets.

The reader's whole job is to be unable to walk past something quietly, so most of what is below
asserts a refusal. The shapes it reads rather than refuses are asserted against the real compose
files at the end, because a reader that agreed with every fixture in this file and with none of
the tree would leave the gate above it green over nothing.
"""

from pathlib import Path

import pytest

from composefiles import compose_files
from composestarts import ComposeStartError, Started, read_starts, unquote

REPO_ROOT = Path(__file__).resolve().parents[2]

BLOCKS = """\
name: cortex

x-anchor: &anchor "/srv"

services:
  brain:
    environment:
      CORTEX_ONE: "first"
      CORTEX_FOLDED: >-
        {"endpoint": "http://elsewhere:9000",
        "note": "over two lines"}
      CORTEX_TWO: 'second'
    depends_on:
      llama:
        condition: service_healthy

  llama:
    image: "ghcr.io/ggml-org/llama.cpp:server"
    command:
      # a comment inside the block
      - "--model"
      - "/models/pick.gguf"
      - >-
        one folded
        item
    ports:
      - "127.0.0.1:8082:8082"
"""


def _one(text: str) -> Started:
    """The only service one fixture declares, so a test can assert on it without indexing twice."""
    starts = read_starts(text)
    assert len(starts) == 1, starts
    return starts[0]


def _named(text: str, service: str) -> Started:
    """The one service of ``text`` called ``service``, which several fixtures declare two of."""
    found = [started for started in read_starts(text) if started.service == service]
    assert len(found) == 1, found
    return found[0]


def _service(body: str) -> str:
    """One service written under a services block, which is the shape most fixtures need."""
    return f"services:\n  one:\n{body}"


# ── what a service is started with ─────────────────────────────────────────────


def test_a_command_written_as_a_block_of_items_is_read_in_order() -> None:
    assert _named(BLOCKS, "llama").command == (
        "--model",
        "/models/pick.gguf",
        "one folded item",
    )


def test_a_command_written_as_an_inline_list_is_read_the_same_way() -> None:
    """The base file and the email sidecar both write one, so both spellings are one answer."""
    started = _one(_service('    command: ["redis-server", "--appendonly", "yes"]\n'))
    assert started.command == ("redis-server", "--appendonly", "yes")


def test_a_service_that_declares_no_command_says_so_rather_than_saying_nothing() -> None:
    """None and an empty command are different answers: an override re-opening a service runs
    the base file's container, and a command with no items would be a container started bare."""
    assert _named(BLOCKS, "brain").command is None


def test_a_command_key_with_nothing_under_it_is_an_empty_command_and_not_an_absent_one() -> None:
    assert _one(_service('    command:\n    image: "x"\n')).command == ()


def test_a_trailing_comment_on_the_command_key_does_not_become_a_command() -> None:
    assert _one(_service('    command: # the items are below\n      - "--jinja"\n')).command == (
        "--jinja",
    )


# ── what environment a service is given ────────────────────────────────────────


def test_an_environment_entry_is_read_with_its_quotes_dropped() -> None:
    assert _named(BLOCKS, "brain").environment[0] == ("CORTEX_ONE", "first")
    assert _named(BLOCKS, "brain").environment[2] == ("CORTEX_TWO", "second")


def test_an_environment_value_folded_over_several_lines_is_read_as_one_value() -> None:
    """The roster override writes one JSON object this way, which is the only way to write one."""
    folded = dict(_named(BLOCKS, "brain").environment)["CORTEX_FOLDED"]
    assert folded == '{"endpoint": "http://elsewhere:9000", "note": "over two lines"}'


def test_a_block_under_some_other_service_key_is_not_read_as_environment() -> None:
    """`depends_on:` opens a block of its own, and nothing in it is a value the service gets."""
    assert [key for key, _ in _named(BLOCKS, "brain").environment] == [
        "CORTEX_ONE",
        "CORTEX_FOLDED",
        "CORTEX_TWO",
    ]


# ── the shapes it refuses rather than guesses at ───────────────────────────────


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        ("services:\n  one:\n    command: llama-server --model x\n", "neither a list nor a block"),
        ("services:\n  one:\n    command: [not json]\n", "not an inline list"),
        ('services:\n  one:\n    command: {"a": 1}\n', "is not a list"),
        ("services:\n  one:\n    command: [1, 2]\n", "not a string"),
        ("services:\n  one:\n    environment: {A: b}\n", "inline environment"),
        ("services:\n  one:\n    environment:\n      - A=b\n", "written as a list"),
        ("services:\n  one:\n    environment:\n      not a key\n", "not an environment key"),
        ("services:\n  one:\n    command:\n      not an item\n", "not an item of a command"),
        ("services:\n  one: an inline body\n", "inline service body"),
        ("services:\n  one:\n    not a key\n", "not a service key"),
        ("not a top-level key\n", "not a top-level key"),
        ("services:\n  1 is no name:\n", "is not a service name"),
        ("services:\n    one:\n  under nothing:\n", "indented under no service"),
    ],
)
def test_a_shape_this_reader_was_not_taught_is_raised(text: str, detail: str) -> None:
    with pytest.raises(ComposeStartError, match=detail):
        read_starts(text)


def test_an_inline_list_that_is_not_a_list_at_all_is_raised() -> None:
    """`command: [` opens a flow collection JSON cannot finish, which is neither shape."""
    with pytest.raises(ComposeStartError, match="not an inline list"):
        read_starts("services:\n  one:\n    command: [\n")


def test_a_key_outside_the_services_block_declares_no_service() -> None:
    """A top-level block of its own is stepped over, which `volumes:` and the anchors are."""
    assert read_starts("volumes:\n  data:\n    driver: local\n") == ()


# ── the same reader, against the tree it is written for ────────────────────────


def test_every_committed_compose_file_is_a_shape_this_reader_can_read() -> None:
    """A reader that only ever met its own fixtures would be a gate over nothing."""
    read = [
        started
        for path in compose_files(REPO_ROOT)
        for started in read_starts(path.read_text(encoding="utf-8"))
    ]
    assert len(read) > 1, "the tree writes several services, so reading one would be a miss"
    assert any(started.command for started in read), "no committed service starts with a command"
    assert any(started.environment for started in read), "no committed service is given anything"


def test_unquote_leaves_an_unquoted_or_half_quoted_word_alone() -> None:
    """One layer, matching, or nothing: a lone quote is part of the word rather than a wrapper."""
    assert unquote('  "quoted"  ') == "quoted"
    assert unquote("'quoted'") == "quoted"
    assert unquote('"half') == '"half'
    assert unquote('"') == '"'
