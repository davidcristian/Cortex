"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    EchoInferenceBackend,
    InferenceBackend,
    SingleResidentModelManager,
    SystemClock,
    TurnEngine,
)
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.config import BrainRuntimeConfig, InferenceConfig, SeamServerConfig
from cortex_orchestrator.server import serve
from cortex_session import RedisSessionStore

# Connect/write/pool time out fast on a dead server; reads have no deadline, since a
# generation may legitimately stream for a long time (the adapter sets no timeout itself).
_LLAMACPP_CONNECT_TIMEOUT_S = 10.0


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


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown."""
    seam_config = SeamServerConfig()
    runtime = BrainRuntimeConfig()
    inference = InferenceConfig()
    store = store_factory(runtime.redis_url)
    backend, close_backend = build_inference_backend(inference, runtime.cortex_model)
    try:
        engine = TurnEngine(store, backend, SystemClock(), cortex_model=runtime.cortex_model)
        await serve(seam_config, engine)
    finally:
        await close_backend()
        await store.aclose()
