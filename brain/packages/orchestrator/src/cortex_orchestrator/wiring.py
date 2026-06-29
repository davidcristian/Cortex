"""Composition root: build the runtime dependencies at the edge, then serve.

The one place that reads config and picks adapters (DI at the edge, AGENTS.md):

- SessionStore  -> `RedisSessionStore` over CORTEX_REDIS_URL, holding the state that
  survives restarts and model swaps (the one hard rule).
- InferenceBackend -> `EchoInferenceBackend`, where the scripted fake IS the runtime
  backend until Slice 4 delivers the real engine adapter (docs/ROADMAP.md).
- Clock -> `SystemClock`.

Everything below the edge receives ports, never settings objects or env access.
"""

from collections.abc import Callable

from cortex_core import EchoInferenceBackend, SystemClock, TurnEngine
from cortex_orchestrator.config import BrainRuntimeConfig, SeamServerConfig
from cortex_orchestrator.server import serve
from cortex_session import RedisSessionStore


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown.

    `store_factory` exists so tests can substitute a fakeredis-backed store; the
    production entrypoint always uses the default. The store's connections are
    released on the way out, whatever ends `serve`.
    """
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
