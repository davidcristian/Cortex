from cortex_core import DecodeStop, StopLedger, StopReason


def test_a_ledger_that_saw_nothing_reports_no_cap() -> None:
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
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.CALLED))
    assert not ledger.capped


def test_a_reason_this_core_cannot_read_is_not_a_cap() -> None:
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.UNKNOWN))
    assert not ledger.capped


def test_one_capped_round_of_several_is_still_a_cap() -> None:
    ledger = StopLedger()
    ledger.observe(DecodeStop(StopReason.CAPPED))
    ledger.observe(DecodeStop(StopReason.FINISHED))
    assert ledger.capped
