"""State-store ports (typing.Protocol): the durable and hot stores the one hard rule protects.

Split from ``ports.py`` for the line cap; ``ports`` re-exports these five, so every existing
``from cortex_core.ports import ...`` keeps resolving. Conversation, memory, subagent-task,
schedule, and mid-turn handoff state each lives only behind one of these ports (AGENTS.md hard
rule): no such state may sit inside a model process, so a model swap is survivable. Method bodies
are one-line ``...`` stubs; failures cross these boundaries exclusively as the typed errors in
``errors.py``.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Protocol

from cortex_core.conversation import Message
from cortex_core.handoff import HandoffRecord, HandoffState
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.schedule import FireOutcome, ScheduleClaim, ScheduledItem
from cortex_core.schedule_transitions import ScheduleEdit
from cortex_core.sessions import SessionSummary
from cortex_core.subagents import SubagentResult, SubagentTask


class SessionStore(Protocol):
    """Source of truth for conversation state; survives model swaps and restarts.

    No conversation state may live anywhere else (AGENTS.md hard rule); a model process holds a
    message only for the in-flight turn. ``append`` persists one message at a session's end;
    ``history`` returns its full history in append order (empty when unknown). ``list_sessions``
    returns recent chats most-recently-active first as ``SessionSummary`` values (ADR-0021) for the
    overlay's chat list/switcher/cycling, unioning the newest ``limit`` with the pinned set so a
    pinned chat lists regardless of recency (pinning addendum). ``set_title`` persists a display
    title (titles addendum) ``list_sessions`` prefers over the first-message derivation.
    ``set_pinned`` pins/unpins a chat (pinning addendum), in ``SessionSummary.pinned``, idempotent.
    ``delete`` HARD-deletes a whole session (history, title, recency member, pin), the "forget"
    write (delete addendum). Failures surface as ``SessionStoreError``.
    """

    async def append(self, session_id: str, message: Message) -> None: ...

    async def history(self, session_id: str) -> Sequence[Message]: ...

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]: ...

    async def set_title(self, session_id: str, title: str) -> None: ...

    async def delete(self, session_id: str) -> None: ...

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None: ...


class MemoryStore(Protocol):
    """Durable, cross-session memory: append one record, retrieve the top-k, forget a namespace.

    ``add`` persists one ``MemoryRecord`` that the caller builds (id, timestamp, embedding,
    scope), so the store only translates, as ``SessionStore.append`` does. ``search`` returns
    the ``k`` records whose embeddings are most similar to ``embedding``, most-similar first;
    ``scopes`` restricts the candidate set to those namespaces (ADR-0008 scoping addendum) and
    defaults to ``None``, which ranks over ALL memories, the global-space v1 behavior.
    ``delete_scope`` hard-deletes every memory in one namespace and returns how many it removed
    (0 when empty), the forget primitive a session-delete cascade and a per-scope eviction policy
    each named (ADR-0008 delete-scope addendum). It takes a single required scope and no wildcard,
    so a namespace is dropped only when named; a caller must never hand it ``GLOBAL_SCOPE``,
    which would erase the shared space every conversation writes. Failures surface as
    ``MemoryStoreError``.
    """

    async def add(self, record: MemoryRecord) -> None: ...

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]: ...

    async def delete_scope(self, scope: str) -> int: ...


class TaskStore(Protocol):
    """Hot store for in-flight subagent tasks and their results (Redis; ADR-0010).

    A subagent is a stateless function over this store: ``put_task`` persists the delegated
    task, ``get_task`` loads it by id (the runner reads only the store, never cortex memory),
    ``put_result`` persists the outcome, and ``get_result`` returns it for the cortex to read
    (``None`` until the subagent has finished). Task state lives here, never in a model process, per
    the one hard rule, for delegation. Failures surface as ``TaskStoreError``.
    """

    async def put_task(self, task: SubagentTask) -> None: ...

    async def get_task(self, task_id: str) -> SubagentTask | None: ...

    async def put_result(self, result: SubagentResult) -> None: ...

    async def get_result(self, task_id: str) -> SubagentResult | None: ...


class ScheduleStore(Protocol):
    """Durable schedules with a fenced claim→finish protocol (ADR-0025).

    A schedule outlives every model swap and restart (the one hard rule), so items live
    only here. ``claim_due`` claims items due at ``now``, plus FIRING items whose
    ``lease`` expired (a crash or overrun mid-fire), taken oldest-due-first, at most ``limit``,
    each under a fresh fencing token: firing is at-least-once, and a record that fails to
    decode on this path is quarantined (dead-lettered, logged loudly), never a poison pill
    that halts the pass. ``finish`` persists one fire (fire-time taint ORs onto the item;
    ``next_due`` re-arms, ``None`` is terminal and the item is deleted unless deliverable) and
    ``release`` un-claims (FIRING → PENDING, due unchanged); both apply only under the
    claim's token and no-op ``False`` for a stale claimant. ``cancel`` deletes outright, and
    it sticks through an in-flight fire, returning ``False`` only for an unknown id.
    ``snooze`` postpones a one-shot to ``until``; a fired-but-undelivered reminder re-arms
    with deliverability cleared, while a recurring, FIRING, or unknown item answers
    ``False``, and the transition is fenced like the rest (ADR-0025 snooze addendum).
    ``edit`` retexts / re-recurs a non-FIRING item in place (``due_at`` untouched, so the next
    occurrence is unchanged and only future re-arms take the new cadence); the editing turn's
    taint ORs onto the item, and a FIRING or unknown item answers ``False`` (edit addendum).
    ``deliverable`` lists fired reminders awaiting ``ack`` (which clears the slot and
    deletes a DONE one-shot). ``list_active`` is PENDING/FIRING plus deliverable, due
    order. Failures surface as ``ScheduleStoreError``.
    """

    async def add(self, item: ScheduledItem) -> None: ...

    async def get(self, item_id: str) -> ScheduledItem | None: ...

    async def list_active(self) -> Sequence[ScheduledItem]: ...

    async def cancel(self, item_id: str) -> bool: ...

    async def snooze(self, item_id: str, *, until: datetime) -> bool: ...

    async def edit(self, item_id: str, edit: ScheduleEdit) -> bool: ...

    async def claim_due(
        self, now: datetime, *, lease: timedelta, limit: int
    ) -> Sequence[ScheduleClaim]: ...

    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool: ...

    async def release(self, claim: ScheduleClaim) -> bool: ...

    async def deliverable(self) -> Sequence[ScheduledItem]: ...

    async def ack(self, item_id: str) -> bool: ...


class HandoffStore(Protocol):
    """Hot store for the one in-flight brain handoff (Redis; ADR-0030).

    The ``HandoffRecord`` is the mid-turn state the swap must not lose (brief, nonce, taint
    ledger, budget position, tool-loop tail); everything else already lives in the other
    stores, so the swap protocol is a stateless function over this one. ``put`` persists a
    snapshot and ``get`` reads it back (``None`` when unknown or expired); ``transition``
    rewrites just the state, answering ``False`` for an unknown id (a stale claimant is a
    no-op, never an error). ``delete`` removes a record outright, idempotently. ``active``
    returns the one non-terminal record, or ``None``: at most one handoff is in flight at a
    time (one GPU), the conductor checks that here before snapshotting, and boot recovery
    reads it to mark a crash-stranded handoff ``FAILED`` (ADR-0030 decision 4). Terminal
    records are kept briefly for diagnosis (the adapter expires them) and are never
    ``active``. Failures surface as ``HandoffStoreError``.
    """

    async def put(self, record: HandoffRecord) -> None: ...

    async def get(self, handoff_id: str) -> HandoffRecord | None: ...

    async def transition(self, handoff_id: str, state: HandoffState) -> bool: ...

    async def delete(self, handoff_id: str) -> None: ...

    async def active(self) -> HandoffRecord | None: ...
