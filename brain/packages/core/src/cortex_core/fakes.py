"""Reference implementations of the ports (pure, deterministic, fully covered)."""

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError, ToolError, ToolNotFoundError
from cortex_core.inference import (
    DecodeStop,
    GenerationBounds,
    InferenceEvent,
    JsonSchema,
    StopReason,
    TextChunk,
)
from cortex_core.progress import ProgressEvent
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec
from cortex_core.waits import TurnWaits, Wait, WaitHold


class EchoInferenceBackend:
    """A scripted backend: its reply counts the user messages it was given, so it is testable."""

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Stream the scripted reply; the model id and offered tools do not alter the script."""
        del model, tools, schema, bounds
        user_messages = [message for message in messages if message.role is Role.USER]
        if not user_messages:
            msg = "EchoInferenceBackend requires at least one user message in the history"
            raise InferenceError(msg)
        yield TextChunk("reply ")
        yield TextChunk(f"{len(user_messages)}:")
        yield TextChunk(f" {user_messages[-1].text}")
        yield DecodeStop(StopReason.FINISHED)


class InMemoryTaskStore:
    """TaskStore kept in dicts, tested against the same contract as the Redis adapter."""

    def __init__(self) -> None:
        self._tasks: dict[str, SubagentTask] = {}
        self._results: dict[str, SubagentResult] = {}

    async def put_task(self, task: SubagentTask) -> None:
        """Persist one delegated task."""
        self._tasks[task.id] = task

    async def get_task(self, task_id: str) -> SubagentTask | None:
        """Return the task with ``task_id``, or None when unknown."""
        return self._tasks.get(task_id)

    async def put_result(self, result: SubagentResult) -> None:
        """Persist one subagent result."""
        self._results[result.task_id] = result

    async def get_result(self, task_id: str) -> SubagentResult | None:
        """Return the result for ``task_id``, or None until the subagent has finished."""
        return self._results.get(task_id)


_ToolAnswer = str | ToolResult
_ToolHandler = Callable[[Mapping[str, Any]], Awaitable[_ToolAnswer]]


class InMemoryToolRegistry:
    """ToolRegistry kept in a dict, tested against the same contract as the MCP adapter."""

    def __init__(self, tools: Mapping[str, tuple[ToolSpec, _ToolHandler]]) -> None:
        self._tools = dict(tools)
        self._failure: ToolError | None = None

    def serve(self, tools: Mapping[str, tuple[ToolSpec, _ToolHandler]]) -> None:
        """Replace the served tool set from here on: a sidecar whose tools changed mid-turn."""
        self._tools = dict(tools)

    def fail_with(self, error: ToolError) -> None:
        """Make every later call raise ``error``: the registry's backend taken away."""
        self._failure = error

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """List the currently registered tool specs, in insertion order."""
        if self._failure is not None:
            raise self._failure
        return tuple(spec for spec, _ in self._tools.values())

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Run the named tool's handler; raise ToolNotFoundError when it is not registered."""
        if self._failure is not None:
            raise self._failure
        entry = self._tools.get(call.name)
        if entry is None:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        _, handler = entry
        answer = await handler(call.arguments)
        if isinstance(answer, str):
            return ToolResult(call_id=call.id, content=answer)
        return replace(answer, call_id=call.id)


class RecordingAuditSink:
    """ToolAuditSink that keeps invocations in a list so tests can assert the audit trail."""

    def __init__(self) -> None:
        self._records: list[ToolInvocation] = []

    async def record(self, invocation: ToolInvocation) -> None:
        """Append one invocation to the recorded trail."""
        self._records.append(invocation)

    @property
    def records(self) -> Sequence[ToolInvocation]:
        """The invocations recorded so far, in dispatch order."""
        return tuple(self._records)


class RecordingConfirmer:
    """Confirmer that records each request and returns a fixed answer."""

    def __init__(self, *, answer: bool) -> None:
        self._answer = answer
        self._requests: list[ConfirmationRequest] = []

    def answer_with(self, *, approved: bool) -> None:
        """Answer every later ask with ``approved``: the person changing their mind."""
        self._answer = approved

    async def confirm(self, request: ConfirmationRequest) -> bool:
        """Record the request and return the fixed answer."""
        self._requests.append(request)
        return self._answer

    @property
    def requests(self) -> Sequence[ConfirmationRequest]:
        """The confirmation requests received so far, in order."""
        return tuple(self._requests)


class RecordingProgressSink:
    """ProgressSink that records every event and wait, so a test can assert what a turn reported."""

    def __init__(self) -> None:
        self._events: list[ProgressEvent] = []
        self._held: list[Wait] = []
        self.waits = TurnWaits(self.emit)

    async def emit(self, event: ProgressEvent) -> None:
        """Record one emitted progress event."""
        self._events.append(event)

    def hold(self, wait: Wait, *, announce: bool = True) -> AbstractAsyncContextManager[WaitHold]:
        """Record ``wait`` and hold it on this sink's own record."""
        self._held.append(wait)
        return self.waits.hold(wait, announce=announce)

    @property
    def events(self) -> Sequence[ProgressEvent]:
        """The progress events emitted so far, in order."""
        return tuple(self._events)

    @property
    def held(self) -> Sequence[Wait]:
        """Every wait opened on this sink so far, in order."""
        return tuple(self._held)


class RecordingPaceSink:
    """PaceSink that records the results a deep phase reported, in order."""

    def __init__(self) -> None:
        self._verdicts: list[bool] = []

    def note_pace(self, *, spilled: bool) -> None:
        """Record how one handoff's tier ran."""
        self._verdicts.append(spilled)

    @property
    def verdicts(self) -> Sequence[bool]:
        """Every result reported so far, in order, one per handoff that produced a reading."""
        return tuple(self._verdicts)


class SystemClock:
    """Clock backed by the system time, always timezone-aware UTC."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)
