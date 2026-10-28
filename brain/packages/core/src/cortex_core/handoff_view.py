"""What the deep model reads of a handoff: the turn so far, ending with a message to it."""

from collections.abc import Sequence
from dataclasses import replace

from cortex_core.conversation import Message, Role, ToolRun
from cortex_core.escalate import ESCALATION_QUEUED_MSG
from cortex_core.handoff import HandoffRecord
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.tools import ToolCall
from cortex_core.untrusted import USER_DECLINED_MSG

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


def cortex_runs(history: Sequence[Message], record: HandoffRecord) -> tuple[ToolRun, ...]:
    """The tool runs the cortex's reply to this turn made before it handed the turn off."""
    return tuple(
        run
        for message in history
        if message.role is Role.ASSISTANT and message.turn_id == record.handoff_id
        for run in message.runs
    )


def declined_calls(record: HandoffRecord) -> list[ToolCall]:
    """The calls the person pressed Deny on before the handoff, read from the tail's results."""
    declined = {
        message.tool_call_id for message in record.loop_tail if message.text == USER_DECLINED_MSG
    }
    return [
        call for message in record.loop_tail for call in message.tool_calls if call.id in declined
    ]


def forget_asked(record: HandoffRecord) -> bool:
    """Whether the cortex named ``forget_memories`` in a call before it handed the turn off."""
    return any(
        call.name == FORGET_CHOSEN_TOOL_NAME
        for message in record.loop_tail
        for call in message.tool_calls
    )


def deep_tail(record: HandoffRecord) -> tuple[Message, ...]:
    """The record's tail, with the escalation's result addressed to the deep model."""
    taken = HANDOFF_TAKEN_MSG.format(brief=record.brief)
    return tuple(
        replace(message, text=taken) if message.text == ESCALATION_QUEUED_MSG else message
        for message in record.loop_tail
    )
