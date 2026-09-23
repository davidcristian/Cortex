import asyncio
from datetime import UTC, datetime

from cortex_core import ConfirmationRequest
from cortex_orchestrator import RpcConfirmer
from cortex_orchestrator.confirm import OUTCOME_TIMEOUT, OUTCOME_UNAVAILABLE
from cortex_seam import ServerEvent

_REQUEST = ConfirmationRequest(
    tool_name="send_email",
    arguments={"to": "user@example.com", "subject": "hi"},
    reason="needs your approval",
)


def _collecting_confirmer(timeout_s: float = 5.0) -> tuple[RpcConfirmer, list[ServerEvent]]:
    emitted: list[ServerEvent] = []
    return RpcConfirmer(emitted.append, timeout_s=timeout_s), emitted


def _resolutions(emitted: list[ServerEvent]) -> list[tuple[str, str]]:
    """Every ConfirmResolved emitted, as (confirm_id, outcome) in order."""
    return [
        (event.confirm_resolved.confirm_id, event.confirm_resolved.outcome)
        for event in emitted
        if event.WhichOneof("event") == "confirm_resolved"
    ]


async def _emitted_id(emitted: list[ServerEvent]) -> str:
    for _ in range(100):
        if emitted:
            return emitted[0].confirm_request.confirm_id
        await asyncio.sleep(0)
    msg = "the confirm request was never emitted"
    raise AssertionError(msg)


async def test_approval_resolves_true_and_the_request_contains_the_draft() -> None:
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


async def test_timeout_denies_and_tells_the_overlay_the_card_is_dead() -> None:
    confirmer, emitted = _collecting_confirmer(timeout_s=0.01)
    assert await confirmer.confirm(_REQUEST) is False
    assert len(emitted) == 2
    assert _resolutions(emitted) == [(emitted[0].confirm_request.confirm_id, OUTCOME_TIMEOUT)]


async def test_an_unknown_confirm_id_is_ignored() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    confirmer.resolve("not-a-real-id", approved=True)
    confirmer.resolve(confirm_id, approved=False)
    assert await ask is False


async def test_a_second_answer_to_the_same_request_is_ignored() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    confirmer.resolve(confirm_id, approved=False)
    confirmer.resolve(confirm_id, approved=True)
    assert await ask is False


async def test_close_denies_the_pending_request_and_every_later_ask() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    confirmer.close()
    assert await ask is False
    assert _resolutions(emitted) == [(confirm_id, OUTCOME_UNAVAILABLE)]
    assert await confirmer.confirm(_REQUEST) is False
    assert len(emitted) == 2


async def test_close_is_idempotent_over_an_answered_request() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirmer.resolve(await _emitted_id(emitted), approved=True)
    assert await ask is True
    confirmer.close()
    confirmer.close()
    assert _resolutions(emitted) == []


async def test_close_skips_a_future_already_resolved_but_not_yet_collected() -> None:
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
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirm_id = await _emitted_id(emitted)
    ask.cancel()
    await asyncio.wait([ask])
    assert ask.cancelled()
    confirmer.resolve(confirm_id, approved=True)
    assert _resolutions(emitted) == []


async def test_an_answered_request_is_never_resolved_on_the_wire() -> None:
    confirmer, emitted = _collecting_confirmer()
    ask = asyncio.ensure_future(confirmer.confirm(_REQUEST))
    confirmer.resolve(await _emitted_id(emitted), approved=True)
    assert await ask is True
    assert _resolutions(emitted) == []
