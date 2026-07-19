"""The Redis-backed stores the composition root owns, opened and closed as one pair."""

from collections.abc import Callable
from dataclasses import dataclass

from cortex_session import RedisPreferenceStore, RedisSessionStore


@dataclass(frozen=True)
class RedisStores:
    """The conversation state (``SessionStore``) and the user's settings (``PreferenceStore``)."""

    sessions: RedisSessionStore
    preferences: RedisPreferenceStore

    @classmethod
    def open(
        cls,
        url: str,
        store_factory: Callable[[str], RedisSessionStore],
        preference_factory: Callable[[str], RedisPreferenceStore],
    ) -> "RedisStores":
        """Build both stores against the same Redis URL (the factories let tests substitute)."""
        return cls(sessions=store_factory(url), preferences=preference_factory(url))

    async def aclose(self) -> None:
        """Release both stores' connections, at composition-root shutdown."""
        await self.sessions.aclose()
        await self.preferences.aclose()
