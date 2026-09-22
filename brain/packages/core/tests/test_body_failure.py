import pytest

from cortex_core import BodyFailure, BodyGatewayError, body_failure_message

_CAPTURE_LEADS = {
    BodyFailure.UNREACHABLE: "could not reach the body to capture the screen",
    BodyFailure.REFUSED: "the body refused to capture the screen",
    BodyFailure.UNSUPPORTED: "this body has no way to capture the screen",
    BodyFailure.UNREADY: "the host is not in a state to capture the screen",
    BodyFailure.OVERSIZE: (
        "the body could not capture the screen within the size the gRPC link allows"
    ),
    BodyFailure.FAULTED: "the body failed to capture the screen",
}


@pytest.mark.parametrize("kind", list(BodyFailure))
def test_every_kind_has_its_own_lead_and_keeps_the_detail(kind: BodyFailure) -> None:
    message = body_failure_message(BodyGatewayError("why", kind=kind), action="capture the screen")
    assert message == f"{_CAPTURE_LEADS[kind]}: why"


def test_no_two_kinds_share_a_lead() -> None:
    assert len(set(_CAPTURE_LEADS.values())) == len(BodyFailure)


def test_only_the_unreachable_kind_claims_the_body_was_unreachable() -> None:
    claiming = {kind for kind, lead in _CAPTURE_LEADS.items() if "could not reach the body" in lead}
    assert claiming == {BodyFailure.UNREACHABLE}


def test_the_action_is_the_only_thing_a_tool_supplies() -> None:
    err = BodyGatewayError("no device", kind=BodyFailure.UNREADY)
    assert (
        body_failure_message(err, action="control volume")
        == "the host is not in a state to control volume: no device"
    )


def test_an_unclassified_failure_is_a_fault_and_never_an_unreachable_body() -> None:
    assert BodyGatewayError("boom").kind is BodyFailure.FAULTED
    assert (
        body_failure_message(BodyGatewayError("boom"), action="capture the screen")
        == "the body failed to capture the screen: boom"
    )
