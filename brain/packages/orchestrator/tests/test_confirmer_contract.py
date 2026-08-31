"""Both `Confirmer` implementations against the same checks (`confirmer_contract.py`).

The core's `RecordingConfirmer` and the real `SeamConfirmer` with an overlay on the other end of
it. That overlay is the fixture's `emit` callback: it reads the `ConfirmRequest` off the control
path, decodes the card the user would see back into a `ConfirmationRequest`, and answers on the
same call by handing the id to `resolve`, which is exactly what the Converse stream does with the
`ConfirmResponse` it reads. Nothing about the adapter is stubbed; only the person is scripted.

The overlay stays silent by not acting at all, and the adapter's own deadline is what turns that
silence into a denial, so the seam fixture runs on a 10 ms timeout. The adapter's other endings
(the resolution event the overlay is sent for a card it cannot see close, an answer after
`close`, a cancelled ask) stay in `test_confirm.py`, which is where a claim about the stream
belongs.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

import pytest
from confirmer_contract import ALL_CHECKS, Check, ConfirmerUnderTest

from cortex_core import ConfirmationRequest, RecordingConfirmer
from cortex_orchestrator import SeamConfirmer
from cortex_seam import ServerEvent

type Build = Callable[[], ConfirmerUnderTest]

# Long enough that a scheduled answer always arrives first, short enough that the silent check
# costs 10 ms. The adapter's own suite uses the same order of magnitude for its timeout case.
_TIMEOUT_S = 0.01


def _recording() -> ConfirmerUnderTest:
    confirmer = RecordingConfirmer(answer=True)
    return ConfirmerUnderTest(
        confirmer=confirmer,
        will_approve=lambda: confirmer.answer_with(approved=True),
        will_refuse=lambda: confirmer.answer_with(approved=False),
        # A fake has no overlay that can fall silent, so it is scripted with the denial that
        # silence produces.
        will_say_nothing=lambda: confirmer.answer_with(approved=False),
        shown=lambda: confirmer.requests,
    )


def _seam() -> ConfirmerUnderTest:
    """The real adapter with a scripted overlay answering on the stream's control path."""
    shown: list[ConfirmationRequest] = []
    person = {"approves": True, "silent": False}
    holder: list[SeamConfirmer] = []

    def emit(event: ServerEvent) -> None:
        if event.WhichOneof("event") != "confirm_request":
            return
        card = event.confirm_request
        arguments: Mapping[str, Any] = json.loads(card.arguments_json)
        shown.append(
            ConfirmationRequest(tool_name=card.tool_name, arguments=arguments, reason=card.reason)
        )
        if not person["silent"]:
            holder[0].resolve(card.confirm_id, approved=person["approves"])

    confirmer = SeamConfirmer(emit, timeout_s=_TIMEOUT_S)
    holder.append(confirmer)

    return ConfirmerUnderTest(
        confirmer=confirmer,
        will_approve=lambda: person.update(approves=True),
        will_refuse=lambda: person.update(approves=False),
        will_say_nothing=lambda: person.update(silent=True),
        shown=lambda: tuple(shown),
    )


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_recording, _seam], ids=["recording", "seam"])
async def test_the_contract_holds(check: Check, build: Build) -> None:
    await check(build())
