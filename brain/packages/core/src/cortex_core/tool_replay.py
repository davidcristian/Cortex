"""Record the tool calls a turn ran, and replay them in later turns as calls with outcomes."""

from collections.abc import Sequence

from cortex_core.conversation import Message, Role, ToolRun
from cortex_core.events import ToolOutcome, TurnEvent
from cortex_core.tool_round import call_message
from cortex_core.tools import ToolCall

REPLAYED_OK = "This call ran and succeeded in an earlier turn. Its result is not kept."
REPLAYED_FAILED = (
    "This call did not succeed in an earlier turn: it failed, was refused or the user declined "
    "it. Its result is not kept."
)


class RunLog:
    """The tool runs one turn's events announce, gathered for the reply the turn stores."""

    def __init__(self) -> None:
        self._runs: list[ToolRun] = []

    def note(self, event: TurnEvent) -> TurnEvent:
        """Record ``event`` when it ends a tool call, and return it unchanged."""
        if isinstance(event, ToolOutcome):
            self._runs.append(ToolRun(name=event.tool_name, ok=event.ok))
        return event

    @property
    def runs(self) -> tuple[ToolRun, ...]:
        return tuple(self._runs)


def replay_runs(history: Sequence[Message]) -> list[Message]:
    """``history`` with the runs each reply records put before it as calls and their outcomes."""
    replayed: list[Message] = []
    for index, message in enumerate(history):
        if message.runs:
            replayed.extend(_run_steps(message, index))
        replayed.append(message)
    return replayed


def _run_steps(reply: Message, index: int) -> list[Message]:
    """One call step naming every run, then one fixed outcome text per call."""
    calls = [
        ToolCall(id=f"replay-{index}-{n}", name=run.name, arguments={})
        for n, run in enumerate(reply.runs)
    ]
    steps = [call_message("", calls, reply.at, reply.turn_id)]
    steps.extend(
        Message(
            role=Role.TOOL,
            text=REPLAYED_OK if run.ok else REPLAYED_FAILED,
            at=reply.at,
            turn_id=reply.turn_id,
            tool_call_id=call.id,
        )
        for call, run in zip(calls, reply.runs, strict=True)
    )
    return steps
