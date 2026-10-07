"""One turn at a time per session, across every stream that names the session."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from cortex_core.events import TurnEvent
from cortex_core.images import ImagePart
from cortex_core.ports import TurnRunner


class SessionTurnLocks:
    """A lock per session with a turn running or waiting, dropped with its last turn."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._users: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._locks)

    @asynccontextmanager
    async def hold(self, session_id: str) -> AsyncGenerator[None]:
        """Wait for the session's turn ahead, if any, then hold the session until exit."""
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        self._users[session_id] = self._users.get(session_id, 0) + 1
        try:
            async with lock:
                yield
        finally:
            self._users[session_id] -= 1
            if self._users[session_id] == 0:
                del self._users[session_id]
                del self._locks[session_id]


class SerialTurnRunner:
    """A ``TurnRunner`` that runs a session's turns one after another, each with its writes."""

    def __init__(self, inner: TurnRunner, locks: SessionTurnLocks) -> None:
        self._inner = inner
        self._locks = locks

    @property
    def inner(self) -> TurnRunner:
        """The runner each turn runs through once it holds its session."""
        return self._inner

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str, images: tuple[ImagePart, ...] = ()
    ) -> AsyncGenerator[TurnEvent, None]:
        """Run ``inner``'s turn once every earlier turn on ``session_id`` has stored its reply."""
        async with self._locks.hold(session_id):
            events = self._inner.handle_turn(session_id, text, turn_id=turn_id, images=images)
            try:
                async for event in events:
                    yield event
            finally:
                await events.aclose()
