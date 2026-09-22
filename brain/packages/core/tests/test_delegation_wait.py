from cortex_core import DELEGATING, QUEUED, StatusUpdate, TurnWaits, Wait
from cortex_core.delegation_wait import DelegationBoard, batch_wait


def test_a_batch_with_any_subtask_waiting_for_room_is_queued() -> None:
    assert batch_wait(3, 0) == Wait(QUEUED, "3 subtasks waiting for room to run")
    assert batch_wait(1, 0) == Wait(QUEUED, "1 subtask waiting for room to run")
    assert batch_wait(1, 2) == Wait(QUEUED, "2 subtasks running, 1 waiting for room to run")
    assert batch_wait(2, 1) == Wait(QUEUED, "1 subtask running, 2 waiting for room to run")


def test_a_batch_with_every_subtask_admitted_is_delegating() -> None:
    assert batch_wait(0, 2) == Wait(DELEGATING, "2 subtasks running")
    assert batch_wait(0, 1) == Wait(DELEGATING, "1 subtask running")


async def test_the_board_moves_each_subtask_from_queued_to_running_to_gone() -> None:
    sent: list[StatusUpdate] = []

    async def emit(event: StatusUpdate) -> None:
        sent.append(event)

    waits = TurnWaits(emit)
    async with waits.hold(batch_wait(2, 0)) as hold:
        board = DelegationBoard(hold, 2)
        first, second = board.subtask(), board.subtask()
        await first.admitted()
        assert waits.current() == batch_wait(1, 1)
        await second.ended()
        assert waits.current() == batch_wait(0, 1)
        await first.ended()
        assert waits.current() == batch_wait(0, 1)
    assert [event.detail for event in sent] == [
        "2 subtasks waiting for room to run",
        "1 subtask running, 1 waiting for room to run",
        "1 subtask running",
    ]
