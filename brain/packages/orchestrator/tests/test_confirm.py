"""Behavior of SeamConfirmer: emit one ConfirmRequest, await the answer, fail closed.

The stream-level round-trips (a real gated tool through converse()) live in
test_converse_confirm.py; these tests pin the adapter's own contract.
"""

import asyncio
from datetime import UTC, datetime

from cortex_core import ConfirmationRequest
from cortex_orchestrator import SeamConfirmer
from cortex_seam import ServerEvent

_REQUEST = ConfirmationRequest(
    tool_name="send_email",
    arguments={"to": "user@example.com", "subject": "hi"},
    reason="needs your approval",
)


def _collecting_confirmer(timeout_s: float = 5.0) -> tuple[SeamConfirmer, list[ServerEvent]]:
    emitted: list[ServerEvent] = []
    return SeamConfirmer(emitted.append, timeout_s=timeout_s), emitted


async def _emitted_id(emitted: list[ServerEvent]) -> str:
    # The confirm task emits on its first step; a single scheduler yield lets it run.
    for _ in range(100):
        if emitted:
            return emitted[0].confirm_request.confirm_id
        await asyncio.sleep(0)
    msg = "the confirm request was never emitted"
    raise AssertionError(msg)


async def test_approval_resolves_true_and_the_request_carries_the_draft() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    request = emitted[0].confirm_request
    assert request.tool_name == "send_email"
    assert request.arguments_json == '{"to": "user@example.com", "subject": "hi"}'
    assert request.reason == "needs your approval"
    confirmer.resolve(confirm_id, approved=True)
    assert await ask is True


async def test_denial_resolves_false() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirmer.resolve(await _emitted_id(emitted), approved=False)
    assert await ask is False


async def test_timeout_denies() -> None:
    confirmer, emitted = _collecting_confirmer(timeout_s=0.01)
    assert await confirmer.confirm(_REQUEST) is False
    assert len(emitted) == 1  # the request went out; the answer never came


async def test_an_unknown_confirm_id_is_ignored() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    confirmer.resolve("not-a-real-id", approved=True)  # a stale/forged answer resolves nothing
    confirmer.resolve(confirm_id, approved=False)
    assert await ask is False


async def test_a_second_answer_to_the_same_request_is_ignored() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    confirmer.resolve(confirm_id, approved=False)
    confirmer.resolve(confirm_id, approved=True)  # the first answer stands (future is done)
    assert await ask is False


async def test_close_denies_the_pending_request_and_every_later_ask() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    await _emitted_id(emitted)
    confirmer.close()  # client input ended: no answer can ever arrive
    assert await ask is False
    assert await confirmer.confirm(_REQUEST) is False  # closed: denied without emitting
    assert len(emitted) == 1


async def test_close_is_idempotent_over_an_answered_request() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirmer.resolve(await _emitted_id(emitted), approved=True)
    assert await ask is True
    confirmer.close()  # nothing pending; must not blow up
    confirmer.close()


async def test_close_skips_a_future_already_resolved_but_not_yet_collected() -> None:
    # resolve() then close() before the awaiting task runs: close sees a done future and
    # must leave it alone (the done-future branch of the close loop).
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirmer.resolve(await _emitted_id(emitted), approved=True)
    confirmer.close()
    assert await ask is True


async def test_an_undumpable_argument_is_stringified_never_a_crash() -> None:
    confirmer, emitted = _collecting_confirmer()
    when = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    ask = asyncio.ensure_future(
        confirmer.confirm(ConfirmationRequest(tool_name="t", arguments={"at": when}, reason="r"))
    )
    confirm_id = await _emitted_id(emitted)
    assert "2026-07-12" in emitted[0].confirm_request.arguments_json
    confirmer.resolve(confirm_id, approved=False)
    assert await ask is False


async def test_cancellation_deregisters_the_pending_request() -> None:
    # The turn dying mid-confirm (Cancel / stream teardown) propagates out of confirm();
    # the request deregisters, so a late answer is a stale id and resolves nothing.
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    ask.cancel()
    await asyncio.wait([ask])
    assert ask.cancelled()
    confirmer.resolve(confirm_id, approved=True)  # ignored: nothing pending anymore
