"""Behaviour of the reader that says what a roster on a page names.

Two questions, kept apart on purpose: where a roster is written (a passage bounded by two phrases
the document carries) and how a name is spelled inside it (a bullet's first code span, or every
code span matching the roster's own pattern). Every case below is an edit somebody could really
make to a module contract, since that is the only kind of edit this reader ever sees.
"""

import re

import pytest

from rosternames import BULLET, CODE_SPAN, Bare, Bulleted, PassageError, Spelled, names, passage

PAGE = """\
# scripts/ (`repo-gates`)

**Public contract** (all are CLIs, with `linecap.py` and `dashcheck.py`). Two modules here
have no CLI: `couplings.py` is the vocabulary and `registry.py` names the parts.

- `linecap.py [--root DIR]` implements AGENTS.md gate 1. Scans three toolchains.

**Live checks**. The ignored tests, run by `just seam-health`:

```sh
cargo test -p body-rpc --test live -- --ignored
```

- `the_brain_answers` calls `Health` and asserts `ready`.
- `the_probe_gives_up` dials `http://127.0.0.1:1` and stays inside the budget.

Being ignored, they never run in CI.
"""

MODULE = re.compile(r"[a-z_]+\.py")


def bullets() -> str:
    """The live-checks passage of the page above, the one both spellings are read out of."""
    return passage(PAGE, "**Live checks**", "Being ignored, they never run in CI")


# ── where a roster is written ──────────────────────────────────────────────────


def test_a_passage_is_the_run_between_its_two_phrases() -> None:
    found = passage(PAGE, "**Public contract**", "- `linecap.py [--root DIR]`")
    assert found.startswith("**Public contract**")
    assert "registry.py" in found
    assert "the_brain_answers" not in found


def test_an_opening_phrase_the_document_lost_is_named() -> None:
    """The shape a rewrite makes: the roster is still there and its boundary is not."""
    with pytest.raises(PassageError, match="opening phrase 'Interface contract' appears 0"):
        passage(PAGE, "Interface contract", "Being ignored, they never run in CI")


def test_a_closing_phrase_the_document_lost_is_named() -> None:
    with pytest.raises(PassageError, match="closing phrase 'Being ignored, they never run"):
        passage(PAGE, "**Live checks**", "Being ignored, they never run in the gate")


def test_a_phrase_the_document_started_carrying_twice_is_refused() -> None:
    """An ambiguous boundary is no boundary: two runs are two answers and neither is the roster."""
    doubled = PAGE + "\n**Live checks** are described above.\n"
    with pytest.raises(PassageError, match="appears 2 time"):
        passage(doubled, "**Live checks**", "Being ignored, they never run in CI")


def test_a_closing_phrase_written_before_its_opening_one_is_refused() -> None:
    with pytest.raises(PassageError, match="is written before the opening phrase"):
        passage(PAGE, "Being ignored, they never run in CI", "**Live checks**")


def test_a_passage_that_would_be_empty_is_refused_rather_than_read_as_none() -> None:
    """Both phrases resolving to one point is the degenerate case, and an empty roster passes."""
    with pytest.raises(PassageError, match="is written before the opening phrase"):
        passage(PAGE, "**Live checks**", "**Live checks**")


# ── how a name is spelled inside it ────────────────────────────────────────────


def test_a_bulleted_roster_names_the_first_code_span_of_every_bullet() -> None:
    assert names(bullets(), Bulleted()) == ["the_brain_answers", "the_probe_gives_up"]


def test_a_bulleted_roster_ignores_the_code_spans_its_prose_carries() -> None:
    """The prose beside a name is free, which is the whole reason this list is written by hand."""
    assert "Health" not in names(bullets(), Bulleted())


def test_a_bullet_that_opens_without_a_name_is_a_fault_and_not_a_skip() -> None:
    """Skipping it would leave a member outside the roster, which is the silence being closed."""
    unnamed = bullets().replace("- `the_probe_gives_up`", "- the probe gives up")
    with pytest.raises(PassageError, match="opens with no name"):
        names(unnamed, Bulleted())


def test_a_spelled_roster_takes_every_code_span_matching_its_pattern() -> None:
    written = passage(PAGE, "**Public contract**", "- `linecap.py [--root DIR]`")
    assert names(written, Spelled(pattern=MODULE)) == [
        "linecap.py",
        "dashcheck.py",
        "couplings.py",
        "registry.py",
    ]


def test_a_spelled_roster_refuses_a_span_that_only_contains_a_name() -> None:
    """A path or a flag beside a module name is a mention of it, never a roster entry."""
    written = "`scripts/linecap.py` and `linecap.py [--root DIR]` and `linecap.py`"
    assert names(written, Spelled(pattern=MODULE)) == ["linecap.py"]


def test_a_spelled_roster_reads_a_name_written_twice_twice() -> None:
    """The scan compares sets; the reader reports the page, so a repeat is not hidden here."""
    assert names("`a.py` then `a.py`", Spelled(pattern=MODULE)) == ["a.py", "a.py"]


def test_a_bare_roster_takes_every_whole_word_matching_its_pattern() -> None:
    """The shape a repo map needs: plain text in columns, where a backtick would be a backtick."""
    mapped = """\
scripts/          repo gates: linecap.py (300-line cap), dashcheck.py (no dash as
                  punctuation) + couplings.py (the vocabulary)
"""
    assert names(mapped, Bare(pattern=MODULE)) == ["linecap.py", "dashcheck.py", "couplings.py"]


def test_a_bare_roster_ignores_a_name_sitting_inside_a_longer_word() -> None:
    """The guard the other two shapes get from their own delimiters and this one has to carry.

    Three edges, because a word character is three things here: a letter the pattern will not
    take, a digit, and the underscore a file name is as likely to end on as to start with.
    """
    assert names("test_linecap.pyc is not a module", Bare(pattern=MODULE)) == []
    assert names("R2linecap.py is not one either", Bare(pattern=MODULE)) == []
    assert names("linecap.py_old is a copy of one", Bare(pattern=MODULE)) == []


def test_a_bare_name_is_read_at_either_end_of_its_passage() -> None:
    """A passage opening or closing on a name has no character to guard against, and is not one."""
    assert names("linecap.py", Bare(pattern=MODULE)) == ["linecap.py"]


def test_a_bare_roster_reads_a_path_as_the_name_it_ends_with() -> None:
    """A slash is not a word character, so `scripts/linecap.py` in a map is that module named."""
    assert names("scripts/linecap.py holds the cap", Bare(pattern=MODULE)) == ["linecap.py"]


def test_a_bare_roster_does_not_care_whether_a_name_is_in_a_code_span() -> None:
    """It exists for pages with no spans, and a page mixing the two is one roster either way."""
    assert names("`linecap.py` and linecap.py", Bare(pattern=MODULE)) == [
        "linecap.py",
        "linecap.py",
    ]


def test_a_passage_with_no_bullets_at_all_names_nothing() -> None:
    assert names("no list here, only `prose.py`", Bulleted()) == []


def test_a_starred_bullet_is_a_bullet() -> None:
    """Both markdown bullet markers, since a document may write either and mean one list."""
    assert names("* `starred.py` counts too", Bulleted()) == ["starred.py"]


# ── the shapes the two patterns are written against ────────────────────────────


def test_a_code_span_stops_at_its_own_backtick() -> None:
    assert [found.group(1) for found in CODE_SPAN.finditer("`one` and `two`")] == ["one", "two"]


def test_a_bullet_is_read_from_the_marker_and_not_from_the_indent() -> None:
    """An indented bullet is still a bullet: a nested list under a roster is part of it."""
    assert BULLET.match("  - `nested.py` is indented") is not None
    assert BULLET.match("-not a bullet") is None
