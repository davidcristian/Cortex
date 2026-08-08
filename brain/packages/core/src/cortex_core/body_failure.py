"""One sentence per ``BodyFailure``, shared by every built-in over the ``BodyGateway`` port."""

from collections.abc import Mapping

from cortex_core.errors import BodyFailure, BodyGatewayError

_LEADS: Mapping[BodyFailure, str] = {
    BodyFailure.UNREACHABLE: "could not reach the body to {action}",
    BodyFailure.REFUSED: "the body refused to {action}",
    BodyFailure.UNSUPPORTED: "this body has no way to {action}",
    BodyFailure.UNREADY: "the host is not in a state to {action}",
    BodyFailure.OVERSIZE: "the body could not {action} within the size the seam allows",
    BodyFailure.FAULTED: "the body failed to {action}",
}


def body_failure_message(err: BodyGatewayError, *, action: str) -> str:
    """The ``is_error`` content for ``err``: the kind's lead, the action, then the detail."""
    return f"{_LEADS[err.kind].format(action=action)}: {err}"
