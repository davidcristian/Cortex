import asyncio

from cortex_core import (
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    RESIDENCY_SERVING,
    ResidencyQueue,
)
from cortex_core.residency_board import ResidencyBoard


async def _settle(turns: int = 10) -> None:
    for _ in range(turns):
        await asyncio.sleep(0)


async def _board_in_scope() -> ResidencyBoard:
    board = ResidencyBoard("cortex")
    await board.enter_scope("brain")
    await board.publish(None, RESIDENCY_LOADING)
    return board


async def test_the_board_is_a_residency_queue() -> None:
    queue: ResidencyQueue = ResidencyBoard("cortex")

    assert not queue.blocks("cortex")
    assert not queue.restoring()


async def test_a_scope_is_restoring_from_the_swap_back_until_it_ends() -> None:
    board = await _board_in_scope()
    assert not board.restoring()
    await board.publish("brain", RESIDENCY_DEEP)
    assert not board.restoring()

    await board.publish(None, RESIDENCY_RESTORING)
    assert board.restoring()
    await board.publish("cortex", RESIDENCY_SERVING)
    assert board.restoring()

    await board.leave_scope()
    assert not board.restoring()


async def test_a_failed_swap_back_still_reads_as_restoring_until_the_scope_ends() -> None:
    board = await _board_in_scope()
    await board.publish(None, RESIDENCY_RESTORING)
    await board.publish(None, RESIDENCY_LOST)

    assert board.restoring()


async def test_a_new_scope_starts_before_its_swap_back_whatever_was_published_between() -> None:
    board = await _board_in_scope()
    await board.publish(None, RESIDENCY_RESTORING)
    await board.leave_scope()
    await board.publish(None, RESIDENCY_RESTORING)

    await board.enter_scope("brain")

    assert not board.restoring()


async def test_waiting_for_a_change_returns_at_once_when_no_scope_blocks() -> None:
    board = ResidencyBoard("cortex")

    async with asyncio.timeout(5.0):
        await board.await_change("cortex", restoring=False)


async def test_waiting_for_a_change_returns_when_the_swap_back_begins() -> None:
    board = await _board_in_scope()
    waiting = asyncio.create_task(board.await_change("cortex", restoring=False))
    await board.publish("brain", RESIDENCY_DEEP)
    await _settle()
    assert not waiting.done()

    await board.publish(None, RESIDENCY_RESTORING)
    async with asyncio.timeout(5.0):
        await waiting
    await board.leave_scope()


async def test_a_wait_begun_during_the_swap_back_returns_only_when_the_scope_ends() -> None:
    board = await _board_in_scope()
    await board.publish(None, RESIDENCY_RESTORING)
    waiting = asyncio.create_task(board.await_change("cortex", restoring=True))
    await board.publish("cortex", RESIDENCY_SERVING)
    await _settle()
    assert not waiting.done()

    await board.leave_scope()
    async with asyncio.timeout(5.0):
        await waiting
