"""Redis adapter for the core's SessionStore port (docs/modules/brain-session.md)."""

from cortex_session.store import DEFAULT_REDIS_URL, RedisSessionStore

__all__ = ["DEFAULT_REDIS_URL", "RedisSessionStore"]
