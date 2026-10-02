"""What the deep model reads of a handoff: the turn so far, ending with a message to it."""

from collections.abc import Sequence
from dataclasses import replace

from cortex_core.conversation import Message, Role
from cortex_core.escalate import ESCALATION_QUEUED_MSG
from cortex_core.handoff import HandoffRecord

HANDOFF_TAKEN_MSG = (
    "The handoff is done: you are the deep model, and this task is now yours. The brief the "
    "assistant wrote for you: {brief}\nAnswer the user's request now, in full. The user has "
    "already been told about the handoff, so do not describe it again."
)


def deep_history(history: Sequence[Message], record: HandoffRecord) -> list[Message]:
    """The stored history without the cortex's reply to this turn, written after the tail."""
    return [
        message
        for message in history
        if message.role is not Role.ASSISTANT or message.turn_id != record.handoff_id
    ]


def deep_tail(record: HandoffRecord) -> tuple[Message, ...]:
    """The record's tail, with the escalation's result addressed to the deep model."""
    taken = HANDOFF_TAKEN_MSG.format(brief=record.brief)
    return tuple(
        replace(message, text=taken) if message.text == ESCALATION_QUEUED_MSG else message
        for message in record.loop_tail
    )
