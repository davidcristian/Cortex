"""Health's reading of the parts a turn needs: the store always, and the cortex's server."""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import SERVING_CHECK_TIMEOUT_S, FencedServingProbe, ServingProbe, ServingWatch
from cortex_inference import LlamaServerProbe
from cortex_orchestrator.config import InferenceConfig
from cortex_session import RedisSessionStore


def build_serving_watch(
    sessions: RedisSessionStore,
    inference: InferenceConfig,
    *,
    between_handoffs: Callable[[], bool] | None,
) -> tuple[ServingWatch, Callable[[], Awaitable[None]]]:
    """The watch ``Health`` reads, with the coroutine that stops it and closes what it holds.

    With escalation on, ``between_handoffs`` is the swap's fence, and a cortex reading across a
    handoff is dropped.
    """
    store = sessions.probe()
    if inference.backend != "llamacpp":
        watch = ServingWatch([store])
        return watch, watch.aclose
    transport = httpx.AsyncHTTPTransport()
    server = LlamaServerProbe(inference.endpoint, transport, timeout_s=SERVING_CHECK_TIMEOUT_S)
    cortex: ServingProbe = (
        server if between_handoffs is None else FencedServingProbe(server, between_handoffs)
    )
    watch = ServingWatch([cortex, store])

    async def close() -> None:
        await watch.aclose()
        await transport.aclose()

    return watch, close
