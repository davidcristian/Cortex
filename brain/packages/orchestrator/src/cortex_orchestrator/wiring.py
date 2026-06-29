"""Composition root: build the runtime dependencies at the edge, then serve.

The one place that reads config and picks adapters (DI at the edge, AGENTS.md):

- SessionStore  -> `RedisSessionStore` over CORTEX_REDIS_URL, holding the state that
  survives restarts and model swaps (the one hard rule).
- InferenceBackend -> `EchoInferenceBackend` by default (GPU-less), or the real
  `LlamaCppBackend` over a `SingleResidentModelManager` when CORTEX_INFERENCE_BACKEND
  is `llamacpp` (ADR-0007). The GPU path is opt-in so CI stays inference-free.
- Memory -> disabled by default, or a `MemoryRecaller` over the `PgVectorMemoryStore` +
  `LlamaCppEmbedder` when CORTEX_MEMORY_BACKEND is `pgvector` (ADR-0008). Opt-in so CI and
  the no-GPU dev loop stay DB-free.
- Clock -> `SystemClock`, shared by the turn engine and the memory recaller.

Everything below the edge receives ports, never settings objects or env access.
"""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    Clock,
    EchoInferenceBackend,
    InferenceBackend,
    MemoryRecaller,
    SingleResidentModelManager,
    SystemClock,
    TurnEngine,
)
from cortex_embedding import LlamaCppEmbedder
from cortex_inference import LlamaCppBackend
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator.config import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
)
from cortex_orchestrator.server import serve
from cortex_session import RedisSessionStore

# Connect/write/pool time out fast on a dead server; reads have no deadline, since a
# generation may legitimately stream for a long time (the adapter sets no timeout itself).
_LLAMACPP_CONNECT_TIMEOUT_S = 10.0
# An embedding is a quick request (no streaming), so it gets a finite overall timeout.
_EMBEDDER_TIMEOUT_S = 30.0


async def _noop_aclose() -> None:
    """Echo holds no resources; the default backend has nothing to release."""
    return


def build_inference_backend(
    config: InferenceConfig, cortex_model: str
) -> tuple[InferenceBackend, Callable[[], Awaitable[None]]]:
    """Pick the backend from config; return it with the coroutine that releases it.

    Returns the no-op closer for Echo (no resources) and the HTTP client's ``aclose`` for
    llama.cpp, so the caller's shutdown path is uniform regardless of which backend ran.
    """
    if config.backend == "llamacpp":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_LLAMACPP_CONNECT_TIMEOUT_S, read=None))
        manager = SingleResidentModelManager(cortex_model, config.endpoint)
        return LlamaCppBackend(manager, client), client.aclose
    return EchoInferenceBackend(), _noop_aclose


async def build_memory(
    config: MemoryConfig, clock: Clock
) -> tuple[MemoryRecaller | None, Callable[[], Awaitable[None]]]:
    """Pick the memory backend from config; return the recaller (or None) with its closer.

    ``none`` disables memory. The DB-less default CI and the no-GPU dev loop run. ``pgvector``
    connects an asyncpg pool and a CPU embedder client; the returned closer releases both.
    """
    if config.backend == "pgvector":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_EMBEDDER_TIMEOUT_S))
        embedder = LlamaCppEmbedder(client, config.embedder_endpoint, model=config.embedder_model)
        store = await PgVectorMemoryStore.connect(config.dsn)

        async def close_memory() -> None:
            await store.aclose()
            await client.aclose()

        return MemoryRecaller(store, embedder, clock), close_memory
    return None, _noop_aclose


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown.

    `store_factory` exists so tests can substitute a fakeredis-backed store; the
    production entrypoint always uses the default. The store's connections and the
    backend's resources are released on the way out, whatever ends `serve`.
    """
    seam_config = SeamServerConfig()
    runtime = BrainRuntimeConfig()
    inference = InferenceConfig()
    memory_config = MemoryConfig()
    clock = SystemClock()
    store = store_factory(runtime.redis_url)
    backend, close_backend = build_inference_backend(inference, runtime.cortex_model)
    memory, close_memory = await build_memory(memory_config, clock)
    try:
        engine = TurnEngine(store, backend, clock, cortex_model=runtime.cortex_model, memory=memory)
        await serve(seam_config, engine)
    finally:
        await close_memory()
        await close_backend()
        await store.aclose()
