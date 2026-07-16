"""Reference implementations of the ports (pure, deterministic, fully covered).

These are not test-only stubs: EchoInferenceBackend and SystemClock are the real
runtime wiring until Slice 4 delivers an engine adapter. The in-memory ``SessionStore``
twin of the Redis adapter lives beside these in ``fakes_session.py`` (line-cap split).
"""

import hashlib
import math
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError, ToolNotFoundError
from cortex_core.inference import InferenceEvent, JsonSchema, TextChunk
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.progress import ProgressEvent
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec

# The fake embedder's default vector width. Small (< a sha256 digest) so distinct texts
# get distinct vectors without cycling the digest; the real nomic model is 768-dim.
_FAKE_EMBED_DIM = 16


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
    ) -> AsyncIterator[InferenceEvent]:
        """Stream the scripted reply; the model id and offered tools do not alter the script."""
        # routing/config concern; the script is model/tool/schema-independent
        del model, tools, schema
        user_messages = [message for message in messages if message.role is Role.USER]
        if not user_messages:
            msg = "EchoInferenceBackend requires at least one user message in the history"
            raise InferenceError(msg)
        yield TextChunk("reply ")
        yield TextChunk(f"{len(user_messages)}:")
        yield TextChunk(f" {user_messages[-1].text}")


class HashEmbedder:
    """Deterministic, I/O-free Embedder for CI and the memory use-case tests.

    Maps text to a fixed-dimension vector via a stable hash: identical text always yields
    the identical vector (so a stored memory is its own strongest cosine match), distinct
    text yields a distinct vector. It carries NO semantics. The real nomic adapter (Slice
    5 host half) is what makes similarity meaningful. Never emits an all-zero vector (each
    component is an integer byte minus 127.5, never exactly zero).
    """

    def __init__(self, dimension: int = _FAKE_EMBED_DIM) -> None:
        self._dimension = dimension

    async def embed(self, text: str) -> Sequence[float]:
        """Return the deterministic pseudo-embedding of ``text``."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple(float(digest[i % len(digest)]) - 127.5 for i in range(self._dimension))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either has no magnitude."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    if magnitude == 0:
        return 0.0
    return dot / magnitude


class InMemoryMemoryStore:
    """MemoryStore held in a list and meant for tests and single-process experiments only.

    Ranks by cosine similarity in Python; it is the behavioral twin of the pgvector adapter
    (Slice 5 host half) behind the same contract. Like ``InMemorySessionStore`` it does NOT
    survive a restart. The durable store is what proves the hard rule.
    """

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    async def add(self, record: MemoryRecord) -> None:
        """Persist one memory record."""
        self._records.append(record)

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        """Return the ``k`` records most similar to ``embedding``, most-similar first.

        ``scopes`` restricts the candidate set to those namespaces (the pgvector
        ``WHERE scope = ANY`` twin, ADR-0008 addendum); ``None`` ranks over all memories.
        """
        allowed = None if scopes is None else set(scopes)
        scored = [
            ScoredMemory(record=record, score=_cosine(embedding, record.embedding))
            for record in self._records
            if allowed is None or record.scope in allowed
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(scored[:k])

    async def delete_scope(self, scope: str) -> int:
        """Hard-delete every memory in ``scope``; return how many were removed (0 if none).

        The in-memory twin of the pgvector ``DELETE FROM memories WHERE scope = $1`` (ADR-0008
        delete-scope addendum): a removed memory simply stops being a search candidate.
        """
        kept = [record for record in self._records if record.scope != scope]
        removed = len(self._records) - len(kept)
        self._records = kept
        return removed


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
