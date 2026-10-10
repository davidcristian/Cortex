"""``ServingProbe`` over a llama.cpp server's own ``GET /health``."""

from dataclasses import dataclass

import httpx

_HEALTH_PATH = "/health"

# Written as numbers rather than through httpx's enum, as in ``trace_probe.py``. llama-server
# answers 503 from the moment it listens until its model is loaded.
_READY_STATUS = 200
_LOADING_STATUS = 503

CORTEX_PART = "the usual assistant's model server"
CORTEX_LOADING = "the usual assistant is still loading"
CORTEX_DOWN = "the usual assistant's model server is not answering, so a turn cannot be answered"

SUBAGENT_PART = "the server for subagent model {name}"
SUBAGENT_LOADING = SUBAGENT_PART + " is still loading, so work delegated to it fails until it is up"
SUBAGENT_DOWN = SUBAGENT_PART + " is not answering, so work delegated to it fails"


@dataclass(frozen=True, slots=True)
class ServerWording:
    """How a probe names its server, and what it says while that server loads or is down."""

    part: str
    loading: str
    down: str


CORTEX_WORDING = ServerWording(part=CORTEX_PART, loading=CORTEX_LOADING, down=CORTEX_DOWN)


def subagent_wording(name: str) -> ServerWording:
    """The wording for the server a subagent roster entry named ``name`` runs on."""
    return ServerWording(
        part=SUBAGENT_PART.format(name=name),
        loading=SUBAGENT_LOADING.format(name=name),
        down=SUBAGENT_DOWN.format(name=name),
    )


class LlamaServerProbe:
    """Asks the server at ``endpoint`` for its health, over a transport the caller closes."""

    def __init__(
        self,
        endpoint: str,
        transport: httpx.AsyncBaseTransport,
        *,
        timeout_s: float,
        wording: ServerWording = CORTEX_WORDING,
    ) -> None:
        self._url = f"{endpoint.rstrip('/')}{_HEALTH_PATH}"
        self._transport = transport
        self._timeout = httpx.Timeout(timeout_s).as_dict()
        self._wording = wording

    @property
    def part(self) -> str:
        """The part this probe asks about."""
        return self._wording.part

    async def fault(self) -> str | None:
        """``None`` when the server says it is ready, and why not otherwise."""
        # The transport rather than a client: a client logs each request at INFO, which for a
        # check every few seconds would be most of the brain's log.
        request = httpx.Request("GET", self._url, extensions={"timeout": self._timeout})
        try:
            response = await self._transport.handle_async_request(request)
            await response.aclose()
        except httpx.HTTPError:
            return self._wording.down
        if response.status_code == _READY_STATUS:
            return None
        if response.status_code == _LOADING_STATUS:
            return self._wording.loading
        return f"{self._wording.part} answered its health check with {response.status_code}"
