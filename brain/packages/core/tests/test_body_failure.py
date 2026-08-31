"""The core half of the kinded ``BodyGateway`` error currency: one sentence per ``BodyFailure``.

The contract the two body built-ins share (ADR-0023's 2026-08-08 addendum), tested here once
rather than twice. The wording is pinned against literals on purpose: this table exists because
a fixed ``could not reach the body`` prefix was shipped in front of failures where the body had
answered, so a lead drifting back toward that claim fails this suite rather than passing as a
different wording.
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
    """Each kind's lead sentence is production's own, with the detail appended to it.

    Walking the enum is what makes the table exhaustive: a kind declared without a lead reaches
    ``_LEADS`` with no entry and raises here rather than shipping."""
    message = body_failure_message(BodyGatewayError("why", kind=kind), action="capture the screen")
    assert message == f"{_CAPTURE_LEADS[kind]}: why"


def test_no_two_kinds_share_a_lead() -> None:
    """No two kinds share a lead sentence, which this test and the one above establish together.

    This one reads the table in this file, which is a harness rather than production, so on its
    own it says nothing about the code. What ties it down is the parametrized test above, which
    requires production's lead to equal this table's for every kind. Taken together: production
    equals a table, and the table has no duplicates, so production has none either. Verified by
    mutation on 2026-08-08, giving two kinds the same lead in production and watching the
    parametrized case above fail.
    """
    assert len(set(_CAPTURE_LEADS.values())) == len(BodyFailure)


def test_only_the_unreachable_kind_claims_the_body_was_unreachable() -> None:
    """Only ``UNREACHABLE`` carries a lead saying the body could not be reached.

    That is the defect this table replaced, written as one invariant rather than six comparisons.
    It reads the harness table, and it is sound for the same reason the test above is.
    """
    claiming = {kind for kind, lead in _CAPTURE_LEADS.items() if "could not reach the body" in lead}
    assert claiming == {BodyFailure.UNREACHABLE}


def test_the_action_is_the_only_thing_a_tool_supplies() -> None:
    """A caller supplies only the action phrase, and every lead is worded around it. The volume
    built-in reads the same table through a different infinitive, so a new body tool gets six
    correct sentences by naming one phrase."""
    err = BodyGatewayError("no device", kind=BodyFailure.UNREADY)
    assert (
        body_failure_message(err, action="control volume")
        == "the host is not in a state to control volume: no device"
    )


def test_an_unclassified_failure_is_a_fault_and_never_an_unreachable_body() -> None:
    """An unclassified failure takes ``FAULTED``, so code that does not classify reports that the
    body failed rather than that it could not be reached, which is the inaccurate claim this
    default replaced."""
    assert BodyGatewayError("boom").kind is BodyFailure.FAULTED
    assert (
        body_failure_message(BodyGatewayError("boom"), action="capture the screen")
        == "the body failed to capture the screen: boom"
    )
