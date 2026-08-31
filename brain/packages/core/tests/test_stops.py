"""Behavior tests for the stop ledger a loop hands its completions' reasons to (ADR-0005).

The ledger is small on purpose, and every case here is about the one thing it must never do:
manufacture a cap. A false cap turns every delegated answer on a quiet build into a refusal, which
is strictly worse than the gap this whole arm closes, so the checks below pin both directions of
each rule rather than only the one the fix is named for.

Mutations proving these tests can fail, each applied to production code alone with the whole
``packages`` suite re-run, so the counts are measured rather than estimated:

- dropping the ``StopReason.CAPPED`` guard in ``observe`` so every stop counts fails **8**: the
  three cases here that hand it a reason which is not a cap, plus five delegation checks whose
  runs answer through ``EchoInferenceBackend``, which reports a stop of its own;
- starting ``_capped`` at ``True`` fails **28**, most of the delegated path, since every run then
  reports a cut reply including the ones whose backend said nothing at all;
- keeping only the last stop, rather than any, fails **2**,
  ``test_one_capped_round_of_several_is_still_a_cap`` here and the tool-loop case beside it in
  ``test_subagent_bounds.py``.
"""

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
    """``UNKNOWN`` states that the reason is unknown, and not knowing is not evidence of a cut."""
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
