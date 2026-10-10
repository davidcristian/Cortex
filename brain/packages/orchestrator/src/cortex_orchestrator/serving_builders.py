"""Health's reading of the parts a turn needs, and of the servers delegated work runs on."""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import SERVING_CHECK_TIMEOUT_S, FencedServingProbe, ServingProbe, ServingWatch
from cortex_inference import LlamaServerProbe, subagent_wording
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_session import RedisSessionStore


def build_serving_watch(
    sessions: RedisSessionStore,
    inference: InferenceConfig,
    subagents: SubagentsConfig,
    *,
    between_handoffs: Callable[[], bool] | None,
) -> tuple[ServingWatch, Callable[[], Awaitable[None]]]:
    """The watch ``Health`` reads, with the coroutine that stops it and closes what it holds.

    With escalation on, ``between_handoffs`` is the swap's fence, and a cortex reading across a
    handoff is dropped. Each roster entry's CPU server is asked for a note.
    """
    transport = httpx.AsyncHTTPTransport()
    probes: list[ServingProbe] = []
    if inference.backend == "llamacpp":
        server = LlamaServerProbe(inference.endpoint, transport, timeout_s=SERVING_CHECK_TIMEOUT_S)
        probes.append(
            server if between_handoffs is None else FencedServingProbe(server, between_handoffs)
        )
    probes.append(sessions.probe())
    noting = [
        LlamaServerProbe(
            entry.endpoint,
            transport,
            timeout_s=SERVING_CHECK_TIMEOUT_S,
            wording=subagent_wording(name),
        )
        for name, entry in subagents.named_roster.items()
    ]
    watch = ServingWatch(probes, noting=noting)

    async def close() -> None:
        await watch.aclose()
        await transport.aclose()

    return watch, close
