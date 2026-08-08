"""The core half of the kinded ``BodyGateway`` error currency: one sentence per ``BodyFailure``.

The contract the two body built-ins share (ADR-0023's 2026-08-08 addendum), tested here once
rather than twice. The wording is pinned against literals on purpose: this table exists because
a fixed ``could not reach the body`` prefix was shipped in front of failures where the body had
answered, so a lead that quietly drifts back toward that claim must be red, not merely different.
"""

import pytest

from cortex_core import BodyFailure, BodyGatewayError, body_failure_message

# Every kind, with the sentence a capture failure of that kind puts in front of the cortex.
_CAPTURE_LEADS = {
    BodyFailure.UNREACHABLE: "could not reach the body to capture the screen",
    BodyFailure.REFUSED: "the body refused to capture the screen",
    BodyFailure.UNSUPPORTED: "this body has no way to capture the screen",
    BodyFailure.UNREADY: "the host is not in a state to capture the screen",
    BodyFailure.OVERSIZE: "the body could not capture the screen within the size the seam allows",
    BodyFailure.FAULTED: "the body failed to capture the screen",
}


@pytest.mark.parametrize("kind", list(BodyFailure))
def test_every_kind_has_its_own_lead_and_keeps_the_detail(kind: BodyFailure) -> None:
    """Walking the enum is what makes the table exhaustive: a kind declared without a lead
    reaches ``_LEADS`` with no entry and raises here rather than shipping."""
    message = body_failure_message(BodyGatewayError("why", kind=kind), action="capture the screen")
    assert message == f"{_CAPTURE_LEADS[kind]}: why"


def test_no_two_kinds_share_a_lead() -> None:
    """The pair above and here is what does the work, and neither half alone would.

    This one reads the table in this file, which is a harness rather than production, so on its
    own it proves nothing about the code. What ties it down is the parametrized test above, which
    requires production's lead to equal this table's for every kind. Composed: production equals a
    table, and the table has no duplicates, so production has none either. Verified by mutation on
    2026-08-08, giving two kinds the same lead in production and watching the row above redden.
    """
    assert len(set(_CAPTURE_LEADS.values())) == len(BodyFailure)


def test_only_the_unreachable_kind_claims_the_body_was_unreachable() -> None:
    """The defect this table replaced, stated as an invariant rather than as six comparisons.

    Reads the harness table for the same reason and is sound for the same reason.
    """
    claiming = {kind for kind, lead in _CAPTURE_LEADS.items() if "could not reach the body" in lead}
    assert claiming == {BodyFailure.UNREACHABLE}


def test_the_action_is_the_only_thing_a_tool_supplies() -> None:
    """The volume built-in reads the same table through a different infinitive, so a new body
    tool inherits six correct sentences by naming one phrase."""
    err = BodyGatewayError("no device", kind=BodyFailure.UNREADY)
    assert (
        body_failure_message(err, action="control volume")
        == "the host is not in a state to control volume: no device"
    )


def test_an_unclassified_failure_is_a_fault_and_never_an_unreachable_body() -> None:
    """The default carries the whole design decision: code that forgets to classify says the
    honest uninformative thing, because the alternative is the falsehood this replaced."""
    assert BodyGatewayError("boom").kind is BodyFailure.FAULTED
    assert (
        body_failure_message(BodyGatewayError("boom"), action="capture the screen")
        == "the body failed to capture the screen: boom"
    )
