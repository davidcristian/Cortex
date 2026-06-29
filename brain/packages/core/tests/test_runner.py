"""Behavior tests for SubagentRunner: a stateless function over the TaskStore (ADR-0010)."""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    ConcurrencyScheduler,
    InferenceBackend,
    InferenceError,
    InferenceEvent,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    SubagentRunner,
    SubagentTask,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
)

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


class FixedClock:
    """A clock pinned to one instant. The runner only needs it to stamp tool messages."""

    def now(self) -> datetime:
        return _AT


class TextBackend:
    """Yields fixed text deltas and records the messages it was handed."""

    def __init__(self, deltas: Sequence[str]) -> None:
        self._deltas = deltas
        self.seen: list[tuple[Message, ...]] = []

    async def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools
        self.seen.append(tuple(messages))
        for delta in self._deltas:
            yield TextChunk(delta)


class ScriptedBackend:
    """Replays a per-step list of events (text deltas and/or tool calls)."""

    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)
        self._call = 0

    async def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools
        step = self._steps[self._call]
        self._call += 1
        for event in step:
            yield event


class FailingBackend:
    """Yields one delta, then fails with the typed inference error."""

    async def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools
        yield TextChunk("partial ")
        msg = "backend exploded"
        raise InferenceError(msg)


async def _read_handler(arguments: Mapping[str, object]) -> str:
    return f"read {arguments['path']}"


def _runner(
    store: InMemoryTaskStore,
    backend: InferenceBackend,
    *,
    tools: ToolDispatcher | None = None,
) -> SubagentRunner:
    return SubagentRunner(
        store,
        backend,
        ConcurrencyScheduler(2),
        FixedClock(),
        subagent_model="subagent",
        tools=tools,
    )


async def test_runs_a_plain_task_and_persists_the_result() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="summarize", context="", at=_AT))
    backend = TextBackend(["sum", "mary"])
    result = await _runner(store, backend).run("t1")
    assert (result.task_id, result.ok, result.output) == ("t1", True, "summary")
    # The cortex reads the outcome back from the store, not from the runner's return.
    assert await store.get_result("t1") == result
    # No context -> a single user message carrying the instruction.
    (messages,) = backend.seen
    assert [m.role for m in messages] == [Role.USER]
    assert messages[0].text == "summarize"


async def test_context_is_passed_as_a_system_message() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t2", instruction="do", context="the context", at=_AT))
    backend = TextBackend(["ok"])
    await _runner(store, backend).run("t2")
    (messages,) = backend.seen
    assert [m.role for m in messages] == [Role.SYSTEM, Role.USER]
    assert (messages[0].text, messages[1].text) == ("the context", "do")


async def test_missing_task_becomes_a_failed_result() -> None:
    store = InMemoryTaskStore()
    result = await _runner(store, TextBackend(["x"])).run("ghost")
    assert (result.ok, result.detail, result.output) == (False, "task not found", "")
    assert await store.get_result("ghost") == result


async def test_inference_failure_becomes_a_failed_result_with_partial_text() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t3", instruction="go", context="", at=_AT))
    result = await _runner(store, FailingBackend()).run("t3")
    assert result.ok is False
    assert result.output == "partial "  # text produced before the failure is kept
    assert "backend exploded" in result.detail
    assert await store.get_result("t3") == result


async def test_tools_enabled_subagent_dispatches_and_audits_its_calls() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t4", instruction="read x", context="", at=_AT))
    backend = ScriptedBackend(
        [
            [TextChunk("looking... "), ToolCall(id="c1", name="read", arguments={"path": "/x"})],
            [TextChunk("done")],
        ]
    )
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )
    dispatcher = ToolDispatcher(registry, sink, FixedClock())
    result = await _runner(store, backend, tools=dispatcher).run("t4")
    assert result.ok is True
    assert result.output == "looking... done"
    # The subagent's own tool call went through the same audited dispatcher.
    (audit,) = sink.records
    assert (audit.name, audit.ok, audit.detail) == ("read", True, "read /x")
