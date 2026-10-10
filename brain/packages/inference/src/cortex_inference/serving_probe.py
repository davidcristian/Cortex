"""``ServingProbe`` over a llama.cpp server's own ``GET /health``."""

import httpx

_HEALTH_PATH = "/health"

# Written as numbers rather than through httpx's enum, as in ``trace_probe.py``. llama-server
# answers 503 from the moment it listens until its model is loaded.
_READY_STATUS = 200
_LOADING_STATUS = 503

CORTEX_PART = "the usual assistant's model server"
CORTEX_LOADING = "the usual assistant is still loading"
CORTEX_DOWN = "the usual assistant's model server is not answering, so a turn cannot be answered"


class LlamaServerProbe:
    """Asks the server at ``endpoint`` for its health, over a transport the caller closes."""

    def __init__(
        self, endpoint: str, transport: httpx.AsyncBaseTransport, *, timeout_s: float
    ) -> None:
        self._url = f"{endpoint.rstrip('/')}{_HEALTH_PATH}"
        self._transport = transport
        self._timeout = httpx.Timeout(timeout_s).as_dict()

    @property
    def part(self) -> str:
        """The part this probe asks about."""
        return CORTEX_PART

    async def fault(self) -> str | None:
        """``None`` when the server says it is ready, and why not otherwise."""
        # The transport rather than a client: a client logs each request at INFO, which for a
        # check every few seconds would be most of the brain's log.
        request = httpx.Request("GET", self._url, extensions={"timeout": self._timeout})
        try:
            response = await self._transport.handle_async_request(request)
            await response.aclose()
        except httpx.HTTPError:
            return CORTEX_DOWN
        if response.status_code == _READY_STATUS:
            return None
        if response.status_code == _LOADING_STATUS:
            return CORTEX_LOADING
        return f"{CORTEX_PART} answered its health check with {response.status_code}"
