"""Health's reading of the parts a turn needs: the store always, the cortex's server when alone."""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import SERVING_CHECK_TIMEOUT_S, ServingWatch
from cortex_inference import LlamaServerProbe
from cortex_orchestrator.config import InferenceConfig
from cortex_session import RedisSessionStore


def build_serving_watch(
    sessions: RedisSessionStore, inference: InferenceConfig, *, escalation: bool
) -> tuple[ServingWatch, Callable[[], Awaitable[None]]]:
    """The watch ``Health`` reads, with the coroutine that stops it and closes what it holds."""
    store = sessions.probe()
    # With escalation on, the residency report states the cortex, and a reading taken while a
    # swap had it stopped would outlive the swap by up to one interval.
    if escalation or inference.backend != "llamacpp":
        watch = ServingWatch([store])
        return watch, watch.aclose
    transport = httpx.AsyncHTTPTransport()
    cortex = LlamaServerProbe(inference.endpoint, transport, timeout_s=SERVING_CHECK_TIMEOUT_S)
    watch = ServingWatch([cortex, store])

    async def close() -> None:
        await watch.aclose()
        await transport.aclose()

    return watch, close
