"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Callable

from cortex_core import EchoInferenceBackend, SystemClock, TurnEngine
from cortex_orchestrator.config import BrainRuntimeConfig, SeamServerConfig
from cortex_orchestrator.server import serve
from cortex_session import RedisSessionStore


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown."""
    seam_config = SeamServerConfig()
    runtime = BrainRuntimeConfig()
    store = store_factory(runtime.redis_url)
    try:
        engine = TurnEngine(
            store, EchoInferenceBackend(), SystemClock(), cortex_model=runtime.cortex_model
        )
        await serve(seam_config, engine)
    finally:
        await store.aclose()
