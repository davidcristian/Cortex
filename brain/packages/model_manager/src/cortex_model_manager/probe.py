"""The readiness seam: whether one child is serving, read over its own ``/health``.

``READY`` on the ``ModelHost`` port means what the compose healthcheck meant before the
supervisor existed (ADR-0030 decision 3), so this asks the same question the same way: ``GET
/health`` on the child's port, 200 and nothing else counts.

The mapping is this coarse because of the measured shape of a real start: the socket refuses
connections for the first fraction of a second, then llama-server answers 503 with
``{"error":{"message":"Loading model",...}}`` for the whole load (seconds to minutes), then 200
``{"status":"ok"}``. Refused and 503 are the same fact to the caller, that the child is not
serving yet, so they collapse into one boolean and the supervisor derives LOADING or FAILED from
the process rather than from the probe alone.
"""

import logging
from http import HTTPStatus
from typing import Protocol

import httpx

_logger = logging.getLogger(__name__)


class HealthProbe(Protocol):
    """Whether the server at ``url`` answers readiness right now."""

    async def serving(self, url: str) -> bool: ...


class HttpHealthProbe:
    """The real probe. Its client carries the timeout, set once at the composition root.

    Every transport failure reads as "not serving": a refused connection is a child whose socket
    is not up yet, and a timeout is a child still loading, both of which answer the only question
    asked here the same way. A failure is logged at debug because it is the normal case for the
    whole duration of a load, and a load takes minutes.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def serving(self, url: str) -> bool:
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as err:
            _logger.debug("a health probe did not answer", extra={"url": url, "error": str(err)})
            return False
        return response.status_code == HTTPStatus.OK
