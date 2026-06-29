"""Reference implementations of the ports (pure, deterministic, fully covered).

These are not test-only stubs: EchoInferenceBackend and SystemClock are the real
runtime wiring until Slice 4 delivers an engine adapter, and InMemorySessionStore
is the contract-test twin of the Redis adapter (``cortex_session``).
"""

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError


class InMemorySessionStore:
    """SessionStore held in a dict and meant for tests and single-process experiments only.

    It intentionally does NOT survive a process restart; the Redis adapter is the
    runtime store precisely because this one cannot prove the hard rule.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message at the end of the session's history."""
        self._sessions.setdefault(session_id, []).append(message)

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        return tuple(self._sessions.get(session_id, ()))


class EchoInferenceBackend:
    """The scripted fake behind CI chat: deterministic, observable state survival.

    For a history whose latest user message has text ``T`` and which contains ``n``
    user messages in total (including the current one), the reply is exactly
    ``"reply {n}: {T}"``, streamed as three deltas. Because ``n`` is derived from
    the store-backed history alone, it keeps counting across a process restart,
    which is what makes external session state observable end to end.
    """

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        """Stream the scripted reply; the logical model id does not alter the script."""
        del model  # routing/config concern; the script is model-independent
        user_messages = [message for message in messages if message.role is Role.USER]
        if not user_messages:
            msg = "EchoInferenceBackend requires at least one user message in the history"
            raise InferenceError(msg)
        yield "reply "
        yield f"{len(user_messages)}:"
        yield f" {user_messages[-1].text}"


class SystemClock:
    """Clock backed by the system time, always timezone-aware UTC."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)
