from datetime import date
from pathlib import Path

import pytest

import backlog


@pytest.mark.parametrize("state", sorted(backlog.OPEN_STATES))
def test_every_open_state_parses_and_names_one_heading(state: str) -> None:
    status = backlog.parse_status(f"open, {state}")
    assert status.state == state
    assert status.on is None
    assert status.detail == ""
    assert status.is_open
    assert status.bucket == backlog.OPEN_STATES[state]


def test_the_two_waiting_states_are_open_states() -> None:
    assert set(backlog.OPEN_STATES) >= backlog.NEEDS_TRIGGER


@pytest.mark.parametrize(
    ("verb", "bucket"),
    [
        ("done", "Done"),
        ("declined", "Declined"),
        ("satisfied", "Satisfied"),
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


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("open, soon", "unknown open state 'soon'"),
        ("open,", "unknown open state ''"),
        ("open, Actionable", "unknown open state 'Actionable'"),
        ("in progress", "unknown status 'in progress'"),
        ("", "unknown status ''"),
        ("never attempted 2026-03-04", "unknown status 'never attempted 2026-03-04'"),
        ("done", "needs a real YYYY-MM-DD date"),
        ("done 2026-13-04", "needs a real YYYY-MM-DD date"),
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
    with pytest.raises(backlog.TaskFileError, match=r"status 'done 2026-13-04' needs a real"):
        backlog.parse_status("done 2026-13-04")


def test_an_unknown_open_state_names_the_states_that_exist() -> None:
    with pytest.raises(backlog.TaskFileError, match=r"expected one of.*'actionable'"):
        backlog.parse_status("open, soon")


def test_ongoing_keeps_the_reason_it_never_closes() -> None:
    status = backlog.parse_status("ongoing: an obligation on every change, not a check")
    assert status.state == "ongoing"
    assert status.detail == "an obligation on every change, not a check"
    assert status.on is None
    assert status.bucket == "Ongoing, never closes"


def test_ongoing_is_counted_as_neither_open_nor_closed() -> None:
    status = backlog.parse_status("ongoing: watched over months of real use")
    assert status.is_ongoing is True
    assert status.is_open is False


@pytest.mark.parametrize(
    "raw",
    [
        "ongoing",
        "ongoing:",
        "ongoing:    ",
    ],
)
def test_an_ongoing_status_without_its_reason_is_rejected(raw: str) -> None:
    with pytest.raises(backlog.TaskFileError, match="why it never closes"):
        backlog.parse_status(raw)


def test_a_refinement_may_not_be_ongoing() -> None:
    text = (
        "# Watch the pool\n\n**Status:** ongoing: watched over months\n"
        "**Area:** memory\n**Origin:** none\n"
    )
    with pytest.raises(backlog.TaskFileError, match="a refinement is work that closes"):
        backlog.parse_task("refinements", Path("001-watch-the-pool.md"), text)


def test_a_host_item_may_be_ongoing() -> None:
    text = (
        "# Watch the pool\n\n**Status:** ongoing: watched over months\n"
        "**Session:** windows-desktop\n**Capability:** W\n**Origin:** none\n"
    )
    task = backlog.parse_task("host", Path("001-watch-the-pool.md"), text)
    assert task.status.is_ongoing is True
