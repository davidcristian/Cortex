"""Behavior tests for the stop ledger a loop hands its completions' reasons to (ADR-0005)."""

from cortex_core import DecodeStop, StopLedger, StopReason


def test_a_ledger_that_saw_nothing_reports_no_cap() -> None:
    """A backend whose engine says nothing leaves the run exactly as it was before this existed."""
    assert not StopLedger().capped


def test_a_capped_completion_is_a_cap() -> None:
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.CAPPED))
    assert ledger.capped


def test_a_completion_that_finished_is_not_a_cap() -> None:
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.FINISHED))
    assert not ledger.capped


def test_a_completion_that_stopped_to_call_a_tool_is_not_a_cap() -> None:
    """Every round of a tool loop but the last ends this way, so reading it as a cut reply would
    fail every tool-using delegated run there is."""
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.CALLED))
    assert not ledger.capped


def test_a_reason_this_core_cannot_read_is_not_a_cap() -> None:
    """``UNKNOWN`` is honest about not knowing, and not knowing is not evidence of a cut."""
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.UNKNOWN))
    assert not ledger.capped


def test_one_capped_round_of_several_is_still_a_cap() -> None:
    """A tool loop decodes several times; material a cut round dropped is missing from the answer
    whether or not the round after it ended cleanly."""
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.CAPPED))
    ledger.observe(DecodeStop(StopReason.FINISHED))
    assert ledger.capped
