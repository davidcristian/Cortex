"""Is a child actually serving? The readiness seam, over the child's own ``/health``."""

import logging
from http import HTTPStatus
from typing import Protocol

import httpx

_logger = logging.getLogger(__name__)


class HealthProbe(Protocol):
    """Whether the server at ``url`` answers readiness right now."""

    async def serving(self, url: str) -> bool: ...


class HttpHealthProbe:
    """The real probe. Its client carries the timeout, set once at the composition root."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def serving(self, url: str) -> bool:
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as err:
            _logger.debug("a health probe did not answer", extra={"url": url, "error": str(err)})
            return False
        return response.status_code == HTTPStatus.OK
