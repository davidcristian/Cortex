"""Reference implementations of the ports (pure, deterministic, fully covered).

These are not test-only stubs: EchoInferenceBackend and SystemClock are the real
runtime wiring until Slice 4 delivers an engine adapter. The in-memory ``SessionStore``
twin of the Redis adapter lives beside these in ``fakes_session.py``, and the memory area's
three (embedder, store, recall trail) in ``fakes_memory.py`` (both line-cap splits).
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError, ToolNotFoundError
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema, TextChunk
from cortex_core.progress import ProgressEvent
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec


class EchoInferenceBackend:
    """The scripted fake behind CI chat: deterministic, observable state survival.

    For a history whose latest user message has text ``T`` and which contains ``n``
    user messages in total (including the current one), the reply is exactly
    ``"reply {n}: {T}"``, streamed as three deltas. Because ``n`` is derived from
    the store-backed history alone, it keeps counting across a process restart,
    which is what makes external session state observable end to end.
    """

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
        # routing/config concern; the script is model/tool/schema-independent
        del model, tools, schema, bounds
        user_messages = [message for message in messages if message.role is Role.USER]
        if not user_messages:
            msg = "EchoInferenceBackend requires at least one user message in the history"
            raise InferenceError(msg)
        yield TextChunk("reply ")
        yield TextChunk(f"{len(user_messages)}:")
        yield TextChunk(f" {user_messages[-1].text}")


class InMemoryTaskStore:
    """TaskStore held in dicts as the contract twin of the Redis adapter (ADR-0010).

    Keeps tasks and results in memory keyed by task id; ``get_task``/``get_result`` return
    ``None`` for an unknown id. Like ``InMemorySessionStore`` it does NOT survive a restart, and
    the Redis adapter is what proves task state survives a swap. For tests and CI only.
    """

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


_ToolHandler = Callable[[Mapping[str, Any]], Awaitable[str]]


class InMemoryToolRegistry:
    """ToolRegistry held in a dict as the contract twin of the MCP adapter (ADR-0009).

    Constructed with ``{name: (spec, handler)}``, where a handler maps call arguments to
    result text. ``invoke`` raises ``ToolNotFoundError`` for an unknown name and lets a
    handler's own ``ToolError`` propagate (the dispatcher turns it into an error result).
    For tests, CI, and single-process experiments, with no server and fully deterministic.
    """

    def __init__(self, tools: Mapping[str, tuple[ToolSpec, _ToolHandler]]) -> None:
        self._tools = dict(tools)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """List the registered tool specs, in insertion order."""
        return tuple(spec for spec, _ in self._tools.values())

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Run the named tool's handler; raise ToolNotFoundError when it is not registered."""
        entry = self._tools.get(call.name)
        if entry is None:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        _, handler = entry
        return ToolResult(call_id=call.id, content=await handler(call.arguments))


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
    """Confirmer that records each request and returns a fixed answer, for gate tests (ADR-0013).

    ``answer=True`` approves every gated call, ``False`` denies; ``requests`` exposes what the
    dispatcher asked to confirm so a test can assert the tool name and the reason shown to the
    user. The real confirmer round-trips the overlay; this one is deterministic and offline.
    """

    def __init__(self, *, answer: bool) -> None:
        self._answer = answer
        self._requests: list[ConfirmationRequest] = []

    async def confirm(self, request: ConfirmationRequest) -> bool:
        """Record the request and return the fixed answer."""
        self._requests.append(request)
        return self._answer

    @property
    def requests(self) -> Sequence[ConfirmationRequest]:
        """The confirmation requests received so far, in order."""
        return tuple(self._requests)


class RecordingProgressSink:
    """ProgressSink that records emitted events so tests can assert what a turn surfaced (ADR-0010).

    The real adapter is the orchestrator's ``SeamProgressSink``, which drops onto a saturated
    stream; this one records unconditionally so a test reads back exactly the batch's scale and
    each subagent's tool steps. Offline and deterministic.
    """

    def __init__(self) -> None:
        self._events: list[ProgressEvent] = []

    async def emit(self, event: ProgressEvent) -> None:
        """Record one emitted progress event."""
        self._events.append(event)

    @property
    def events(self) -> Sequence[ProgressEvent]:
        """The progress events emitted so far, in order."""
        return tuple(self._events)


class SystemClock:
    """Clock backed by the system time, always timezone-aware UTC."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)
