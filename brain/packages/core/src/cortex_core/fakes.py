"""Reference implementations of the ports (pure, deterministic, fully covered).

These are not test-only stubs: EchoInferenceBackend and SystemClock are the real
runtime wiring until Slice 4 delivers an engine adapter. The in-memory ``SessionStore``
twin of the Redis adapter lives beside these in ``fakes_session.py``, and the memory area's
three (embedder, store, recall trail) in ``fakes_memory.py`` (both line-cap splits).
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
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


class EchoInferenceBackend:
    """The scripted fake behind CI chat: deterministic, observable state survival.

    For a history whose latest user message has text ``T`` and which contains ``n``
    user messages in total (including the current one), the reply is exactly
    ``"reply {n}: {T}"``, streamed as three deltas. Because ``n`` is derived from
    the store-backed history alone, it keeps counting across a process restart,
    which is what makes external session state observable end to end.

    It closes with ``DecodeStop(StopReason.FINISHED)``, and that is not the fabrication the
    decode cadence would be here (``fakes_inference.py`` argues at length why this backend must
    never report a rate). The two facts differ in who knows them: a rate is a measurement only a
    real server has taken, so an echo inventing one would put a made-up number in a real log,
    while why this completion ended is something the echo itself decided and can state truthfully.
    It ends because its script does, which is a model ending its own turn. It honours no
    ``bounds``, so it can never end any other way (ADR-0005 finish-reason addendum).
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
        yield DecodeStop(StopReason.FINISHED)


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


_ToolAnswer = str | ToolResult
_ToolHandler = Callable[[Mapping[str, Any]], Awaitable[_ToolAnswer]]


class InMemoryToolRegistry:
    """ToolRegistry held in a dict as the contract twin of the MCP adapter (ADR-0009).

    Constructed with ``{name: (spec, handler)}``, where a handler maps call arguments to
    result text, or to a whole ``ToolResult`` when the tool has to have **run and failed**:
    that is the port's central case (``is_error`` reflects the tool, not the dispatch) and
    text alone cannot say it. The call's own id is stamped on either answer, so a handler
    never has to know it. ``invoke`` raises ``ToolNotFoundError`` for an unknown name and lets
    a handler's own ``ToolError`` propagate (the dispatcher turns it into an error result).
    ``serve`` replaces the tool set mid-run, which is how a test moves a world the port
    promises to re-read, and ``fail_with`` takes the whole registry away the way a dead
    sidecar does. For tests, CI, and single-process experiments, with no server and fully
    deterministic.
    """

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
    """Confirmer that records each request and returns a fixed answer, for gate tests (ADR-0013).

    ``answer=True`` approves every gated call, ``False`` denies; ``requests`` exposes what the
    dispatcher asked to confirm so a test can assert the tool name and the reason shown to the
    user. ``answer_with`` changes the answer between two asks, which the shared contract needs
    because a person is not a constant: the real confirmer's next answer is whatever the overlay
    sends next, and a fake whose answer is fixed at construction cannot be asked twice about two
    different calls. The real confirmer round-trips the overlay; this one is deterministic and
    offline.
    """

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


class RecordingPaceSink:
    """PaceSink that records the verdicts a deep phase published, in order (ADR-0030).

    The contract twin of ``HandoffPace``, which is what a live brain wires. This one keeps every
    verdict, so a test can assert that one handoff published exactly one and which way it went;
    the real record keeps only the answer that still stands, which is a fact about display and
    not about the port. Both are synchronous and neither may await: the phase calls this between
    its stream ending and its reply being persisted.
    """

    def __init__(self) -> None:
        self._verdicts: list[bool] = []

    def note_pace(self, *, spilled: bool) -> None:
        """Record how one handoff's tier ran."""
        self._verdicts.append(spilled)

    @property
    def verdicts(self) -> Sequence[bool]:
        """Every verdict published so far, in order, one per handoff that settled a reading."""
        return tuple(self._verdicts)


class SystemClock:
    """Clock backed by the system time, always timezone-aware UTC."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)
