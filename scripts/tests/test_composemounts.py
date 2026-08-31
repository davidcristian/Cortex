"""Tests for the compose mount reader: what it reads, what it skips, and what it raises on.

The raises matter as much as the reads. This reader is a line walk rather than a YAML parse, so
every shape it has not been taught raises. A reader that walked past a new override's bind mount
without a word would leave `bindcheck.py` passing over that mount forever.
"""

import pytest

from composemounts import ComposeReadError, Mount, read_mounts, strip_quotes

# One service with both mount syntaxes, a named volume, a `ports:` list that must not be read as
# one, and the top-level `volumes:` mapping that declares the named volume.
STACK = """\
services:
  brain:
    # A comment inside the service.
    volumes:
      - type: bind
        source: "${CORTEX_MODELS_DIR:-./models}"
        target: /models
        read_only: true
      - type: volume
        source: cortex-pgdata
        target: /var/lib/postgresql/data
    ports:
      - "127.0.0.1:50051:50051"
  redis:
    volumes:
      - redis-data:/data

volumes:
  redis-data:
"""


def test_reads_the_bind_and_skips_the_volume_and_the_ports() -> None:
    assert read_mounts(STACK) == [Mount(line=5, source="${CORTEX_MODELS_DIR:-./models}")]


def test_a_short_syntax_host_path_is_a_bind() -> None:
    text = "services:\n  tools:\n    volumes:\n      - ./sandbox:/projects:ro\n"
    assert read_mounts(text) == [Mount(line=4, source="./sandbox")]


def test_a_dash_alone_starts_an_entry_whose_keys_follow() -> None:
    text = "services:\n  a:\n    volumes:\n      -\n        type: bind\n        source: ./x\n"
    assert read_mounts(text) == [Mount(line=4, source="./x")]


def test_a_comment_after_the_volumes_key_still_opens_the_block() -> None:
    text = (
        "services:\n  a:\n    volumes: # the only mount\n      - type: bind\n        source: ./x\n"
    )
    assert read_mounts(text) == [Mount(line=4, source="./x")]


def test_a_second_service_reopens_a_block_after_the_first_closes() -> None:
    text = (
        "services:\n"
        "  a:\n"
        "    volumes:\n"
        "      - type: bind\n"
        "        source: ./one\n"
        "  b:\n"
        "    volumes:\n"
        "      - type: bind\n"
        "        source: ./two\n"
    )
    assert read_mounts(text) == [Mount(line=4, source="./one"), Mount(line=8, source="./two")]


def test_a_flush_sequence_is_read_rather_than_walked_past() -> None:
    """Compose accepts sequence items at their key's own indent.

    A block written that way was once skipped entirely by this reader.
    """
    text = "services:\n  a:\n    volumes:\n    - type: bind\n      source: ./x\n"
    assert read_mounts(text) == [Mount(line=4, source="./x")]


def test_a_flush_sequence_still_closes_on_the_next_key_beside_it() -> None:
    """The block ends at the first line that is not one of its items, flush or not."""
    text = 'services:\n  a:\n    volumes:\n    - ./x:/y\n    ports:\n    - "1:2"\n'
    assert read_mounts(text) == [Mount(line=4, source="./x")]


def test_nothing_outside_a_volumes_block_is_read() -> None:
    assert read_mounts("services:\n  a:\n    command:\n      - ./not-a-mount\n") == []


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("services:\n  a:\n    volumes: []\n", "inline volumes list"),
        ("services:\n  a:\n    volumes:\n      - source: ./x\n", "declares no type"),
        ("services:\n  a:\n    volumes:\n      - type: sorcery\n        source: ./x\n", "unknown"),
        ("services:\n  a:\n    volumes:\n      - type: bind\n        target: /x\n", "no source"),
        ('services:\n  a:\n    volumes:\n      - "${X:-./y}:/z"\n', "carries an expansion"),
        ("services:\n  a:\n    volumes:\n      - loose\n", "is not source:target"),
        ("services:\n  a:\n    volumes:\n      - type: bind\n        loose\n", "not a mount key"),
        ("services:\n  a:\n    volumes:\n      - v:/d\n        stray: true\n", "not a mount key"),
        # Flow style: the long syntax written inline. Its first field would otherwise read as a
        # named volume, hiding a real bind mount.
        ("services:\n  a:\n    volumes:\n      - {type: bind, source: ./x}\n", "flow-style"),
        ("services:\n  a:\n    volumes:\n      - [./x, /y]\n", "flow-style"),
    ],
)
def test_a_shape_it_was_not_taught_is_refused(text: str, reason: str) -> None:
    with pytest.raises(ComposeReadError, match=reason):
        read_mounts(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('"./models"', "./models"),
        ("'./models'", "./models"),
        ("  ./models  ", "./models"),
        ('"', '"'),  # one lone quote is not a pair, so it is left exactly as written
        ("\"./a'", "\"./a'"),  # mismatched quotes are not a pair either
    ],
)
def test_strip_quotes_takes_one_matching_pair_and_no_more(text: str, expected: str) -> None:
    assert strip_quotes(text) == expected
