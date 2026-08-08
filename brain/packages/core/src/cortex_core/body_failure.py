"""One sentence per ``BodyFailure``, shared by every built-in over the ``BodyGateway`` port.

The core's half of the kinded error currency (ADR-0023's 2026-08-08 addendum). The adapter
decides *which* kind a failure is; this decides what the cortex is told about it, and it is one
declarative table so the two built-ins cannot drift apart. Each tool supplies only the infinitive
naming what it was doing (``capture the screen``, ``control volume``), so a new body tool inherits
six correct sentences by naming one phrase.

**Why this exists at all.** Both tools used to prefix every failure with ``could not reach the
body``, which was false for all but one kind and reachable on a default install: with
``CORTEX_HOST_CAPTURE`` unset the body answers ``PERMISSION_DENIED`` promptly and precisely, and
the model was told the body was unreachable and then handed the truth after the colon. The lead
now says what happened; the detail after the colon is still the body's own sentence, which stays
the more specific of the two.
"""

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
    """The ``is_error`` content for ``err``: the kind's lead, the action, then the detail.

    ``action`` is an infinitive phrase the lead completes. A kind with no lead raises
    ``KeyError`` rather than degrading quietly, and the test that walks the enum is what keeps
    that from ever shipping: a lead is owed the moment a kind is declared.
    """
    return f"{_LEADS[err.kind].format(action=action)}: {err}"
