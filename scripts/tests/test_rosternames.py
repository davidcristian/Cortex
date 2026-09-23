import re

import pytest

from rosternames import BULLET, CODE_SPAN, Bare, Bulleted, CodeSpans, PassageError, names, passage

PAGE = """\
# scripts/ (`repo-checks`)

**Public contract** (all are CLIs, with `linecap.py` and `dashcheck.py`). Two modules here
have no CLI: `couplings.py` is the vocabulary and `registry.py` names the parts.

- `linecap.py [--root DIR]` implements AGENTS.md gate 1. Scans three toolchains.

**Live checks**. The ignored tests, run by `just rpc-health`:

```sh
cargo test -p body-rpc --test live -- --ignored
```

- `the_brain_answers` calls `Health` and asserts `ready`.
- `the_probe_gives_up` dials `http://127.0.0.1:1` and stays inside the budget.

Being ignored, they never run in CI.
"""

MODULE = re.compile(r"[a-z_]+\.py")


def bullets() -> str:
    """Return the live-checks passage of the page above, which both name forms are read from."""
    return passage(PAGE, "**Live checks**", "Being ignored, they never run in CI")


def test_a_passage_is_the_run_between_its_two_phrases() -> None:
    found = passage(PAGE, "**Public contract**", "- `linecap.py [--root DIR]`")
    assert found.startswith("**Public contract**")
    assert "registry.py" in found
    assert "the_brain_answers" not in found


def test_an_opening_phrase_the_document_lost_is_named() -> None:
    with pytest.raises(PassageError, match="opening phrase 'Interface contract' appears 0"):
        passage(PAGE, "Interface contract", "Being ignored, they never run in CI")


def test_a_closing_phrase_the_document_lost_is_named() -> None:
    with pytest.raises(PassageError, match="closing phrase 'Being ignored, they never run"):
        passage(PAGE, "**Live checks**", "Being ignored, they never run in the gate")


def test_a_phrase_the_document_started_carrying_twice_is_refused() -> None:
    doubled = PAGE + "\n**Live checks** are described above.\n"
    with pytest.raises(PassageError, match="appears 2 time"):
        passage(doubled, "**Live checks**", "Being ignored, they never run in CI")


def test_a_closing_phrase_written_before_its_opening_one_is_refused() -> None:
    with pytest.raises(PassageError, match="is written before the opening phrase"):
        passage(PAGE, "Being ignored, they never run in CI", "**Live checks**")


def test_a_passage_that_would_be_empty_is_refused_rather_than_read_as_none() -> None:
    with pytest.raises(PassageError, match="is written before the opening phrase"):
        passage(PAGE, "**Live checks**", "**Live checks**")


def test_a_bulleted_roster_names_the_first_code_span_of_every_bullet() -> None:
    assert names(bullets(), Bulleted()) == ["the_brain_answers", "the_probe_gives_up"]


def test_a_bulleted_roster_ignores_the_code_spans_its_prose_carries() -> None:
    assert "Health" not in names(bullets(), Bulleted())


def test_a_bullet_that_opens_without_a_name_is_a_fault_and_not_a_skip() -> None:
    unnamed = bullets().replace("- `the_probe_gives_up`", "- the probe gives up")
    with pytest.raises(PassageError, match="opens with no name"):
        names(unnamed, Bulleted())


def test_a_written_roster_takes_every_code_span_matching_its_pattern() -> None:
    written = passage(PAGE, "**Public contract**", "- `linecap.py [--root DIR]`")
    assert names(written, CodeSpans(pattern=MODULE)) == [
        "linecap.py",
        "dashcheck.py",
        "couplings.py",
        "registry.py",
    ]


def test_a_written_roster_refuses_a_span_that_only_contains_a_name() -> None:
    written = "`scripts/linecap.py` and `linecap.py [--root DIR]` and `linecap.py`"
    assert names(written, CodeSpans(pattern=MODULE)) == ["linecap.py"]


def test_a_written_roster_reads_a_name_written_twice_twice() -> None:
    assert names("`a.py` then `a.py`", CodeSpans(pattern=MODULE)) == ["a.py", "a.py"]


def test_a_bare_roster_takes_every_whole_word_matching_its_pattern() -> None:
    mapped = """\
scripts/          repo gates: linecap.py (300-line cap), dashcheck.py (no dash as
                  punctuation) + couplings.py (the vocabulary)
"""
    assert names(mapped, Bare(pattern=MODULE)) == ["linecap.py", "dashcheck.py", "couplings.py"]


def test_a_bare_roster_ignores_a_name_inside_a_longer_word() -> None:
    assert names("test_linecap.pyc is not a module", Bare(pattern=MODULE)) == []
    assert names("R2linecap.py is not one either", Bare(pattern=MODULE)) == []
    assert names("linecap.py_old is a copy of one", Bare(pattern=MODULE)) == []


def test_a_bare_name_is_read_at_either_end_of_its_passage() -> None:
    assert names("linecap.py", Bare(pattern=MODULE)) == ["linecap.py"]


def test_a_bare_roster_reads_a_path_as_the_name_it_ends_with() -> None:
    assert names("scripts/linecap.py holds the cap", Bare(pattern=MODULE)) == ["linecap.py"]


def test_a_bare_roster_does_not_care_whether_a_name_is_in_a_code_span() -> None:
    assert names("`linecap.py` and linecap.py", Bare(pattern=MODULE)) == [
        "linecap.py",
        "linecap.py",
    ]


def test_a_passage_with_no_bullets_at_all_names_nothing() -> None:
    assert names("no list here, only `prose.py`", Bulleted()) == []


def test_a_starred_bullet_is_a_bullet() -> None:
    assert names("* `starred.py` counts too", Bulleted()) == ["starred.py"]


def test_a_code_span_stops_at_its_own_backtick() -> None:
    assert [found.group(1) for found in CODE_SPAN.finditer("`one` and `two`")] == ["one", "two"]


def test_a_bullet_is_read_from_the_marker_and_not_from_the_indent() -> None:
    assert BULLET.match("  - `nested.py` is indented") is not None
    assert BULLET.match("-not a bullet") is None
