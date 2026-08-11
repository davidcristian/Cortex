from datetime import date
from pathlib import Path

import pytest

import backlog

# ── the open half of the status grammar ────────────────────────────────────────


@pytest.mark.parametrize("state", sorted(backlog.OPEN_STATES))
def test_every_open_state_parses_and_names_one_heading(state: str) -> None:
    """An open status carries no date, and each state files under exactly one heading."""
    status = backlog.parse_status(f"open, {state}")
    assert status.state == state
    assert status.on is None
    assert status.detail == ""
    assert status.is_open
    assert status.bucket == backlog.OPEN_STATES[state]


def test_the_two_waiting_states_are_open_states() -> None:
    """A trigger rule spelled over a state nothing can reach would gate nothing."""
    assert set(backlog.OPEN_STATES) >= backlog.NEEDS_TRIGGER


# ── the closed half, and the two states the host backlog adds ──────────────────


@pytest.mark.parametrize(
    ("verb", "bucket"),
    [
        ("landed", "Landed"),
        ("declined", "Declined"),
        ("satisfied", "Satisfied"),
        ("done", "Done"),
    ],
)
def test_a_closed_status_keeps_its_date_and_leaves_the_open_half(verb: str, bucket: str) -> None:
    status = backlog.parse_status(f"{verb} 2026-03-04")
    assert status.state == verb
    assert status.on == date(2026, 3, 4)
    assert status.detail == ""
    assert not status.is_open
    assert status.bucket == bucket


def test_never_attempted_is_open_work_with_no_date() -> None:
    status = backlog.parse_status("never attempted")
    assert (status.state, status.on, status.detail) == ("never attempted", None, "")
    assert status.is_open
    assert status.bucket == "Never attempted"


def test_attempted_keeps_the_date_and_what_happened() -> None:
    status = backlog.parse_status("attempted 2026-03-04, inconclusive: the card was busy")
    assert status.state == "attempted"
    assert status.on == date(2026, 3, 4)
    assert status.detail == "the card was busy"
    assert status.is_open
    assert status.bucket == "Attempted, inconclusive"


# ── what the grammar refuses ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("open, soon", "unknown open state 'soon'"),
        ("open,", "unknown open state ''"),
        ("open, Actionable", "unknown open state 'Actionable'"),
        ("in progress", "unknown status 'in progress'"),
        ("", "unknown status ''"),
        ("never attempted 2026-03-04", "unknown status 'never attempted 2026-03-04'"),
        ("landed", "needs a real YYYY-MM-DD date"),
        ("landed 2026-13-04", "needs a real YYYY-MM-DD date"),
        ("done last Tuesday", "needs a real YYYY-MM-DD date"),
        ("satisfied 04-03-2026", "needs a real YYYY-MM-DD date"),
        ("attempted whenever, inconclusive: the card was busy", "needs a real YYYY-MM-DD date"),
        ("attempted 2026-03-04", "attempted <date>, inconclusive"),
        ("attempted 2026-03-04, inconclusive:", "attempted <date>, inconclusive"),
        ("attempted 2026-03-04, inconclusive:   ", "attempted <date>, inconclusive"),
    ],
)
def test_a_status_outside_the_grammar_is_rejected(raw: str, message: str) -> None:
    with pytest.raises(backlog.TaskFileError, match=message):
        backlog.parse_status(raw)


def test_a_bad_date_is_reported_against_the_whole_status_line() -> None:
    """The line is what a person has to fix, so the message quotes it, not the fragment."""
    with pytest.raises(backlog.TaskFileError, match=r"status 'landed 2026-13-04' needs a real"):
        backlog.parse_status("landed 2026-13-04")


def test_an_unknown_open_state_names_the_states_that_exist() -> None:
    with pytest.raises(backlog.TaskFileError, match=r"expected one of.*'actionable'"):
        backlog.parse_status("open, soon")


# ── the links a task file spends ───────────────────────────────────────────────


def test_local_links_keeps_the_relative_targets_and_drops_the_rest() -> None:
    """Only a relative target can rot on a move, so only those are worth resolving."""
    text = (
        "See [the sibling](002-a-slug.md) and [the decision](../adr/ADR-0001.md#decision-7).\n"
        "Not [the site](https://example.com/x), nor [the plain one](http://example.com/y),\n"
        "nor [a heading](#what-remains), nor [the author](mailto:someone@example.com).\n"
    )
    assert backlog.local_links(text) == ["002-a-slug.md", "../adr/ADR-0001.md"]


def test_local_links_finds_nothing_in_prose_that_links_nowhere() -> None:
    assert backlog.local_links("Plain prose, with brackets [but no target] in it.\n") == []


# ── standing: the host state that is neither open nor closed ───────────────────


def test_standing_keeps_the_reason_it_never_closes() -> None:
    status = backlog.parse_status("standing: an obligation on every change, not a check")
    assert status.state == "standing"
    assert status.detail == "an obligation on every change, not a check"
    assert status.on is None
    assert status.bucket == "Standing, never closes"


def test_standing_is_counted_as_neither_open_nor_closed() -> None:
    status = backlog.parse_status("standing: watched over months of real use")
    assert status.is_standing is True
    assert status.is_open is False


@pytest.mark.parametrize(
    "raw",
    [
        "standing",  # no colon, so it never says why it never closes
        "standing:",
        "standing:    ",
    ],
)
def test_a_standing_status_without_its_reason_is_rejected(raw: str) -> None:
    with pytest.raises(backlog.TaskFileError, match="why it never closes"):
        backlog.parse_status(raw)


def test_a_refinement_may_not_be_standing() -> None:
    text = (
        "# Watch the pool\n\n**Status:** standing: watched over months\n"
        "**Area:** memory\n**Origin:** none\n"
    )
    with pytest.raises(backlog.TaskFileError, match="a refinement is work that closes"):
        backlog.parse_task("refinements", Path("001-watch-the-pool.md"), text)


def test_a_host_item_may_be_standing() -> None:
    text = (
        "# Watch the pool\n\n**Status:** standing: watched over months\n"
        "**Sitting:** windows-desktop\n**Capability:** W\n**Origin:** none\n"
    )
    task = backlog.parse_task("host", Path("001-watch-the-pool.md"), text)
    assert task.status.is_standing is True
