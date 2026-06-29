"""LlamaCppEmbedder: the Embedder port over a llama-server OpenAI /v1/embeddings endpoint.

ADR-0005/0008: embeddings run on their own CPU ``llama-server`` (``-ngl 0``), separate from
the GPU cortex and never routed through the ModelManager (the GPU budget is spent on the
cortex). This adapter is a thin HTTP translator that POSTs one text and returns the
embedding vector; every transport, status, or decode failure crosses the port as
``EmbedderError`` with the cause chained.
"""

from collections.abc import Sequence

import httpx

from cortex_core import EmbedderError

_EMBEDDINGS_PATH = "/v1/embeddings"

# llama-server embeds with whatever model it was started with and ignores this value, but
# the OpenAI schema requires the field; the composition root sets the logical id (ADR-0004).
_DEFAULT_EMBED_MODEL = "embedding"


class LlamaCppEmbedder:
    """Embedder over a CPU llama-server's OpenAI-compatible embeddings endpoint (ADR-0008).

    The ``http_client`` is injected so timeout and transport are configured at the
    composition root. ``endpoint`` is the base URL of the embedding server; ``model`` is the
    logical id sent in the request body (the server ignores it, but the schema requires it).
    """

    def __init__(
        self, http_client: httpx.AsyncClient, endpoint: str, *, model: str = _DEFAULT_EMBED_MODEL
    ) -> None:
        self._client = http_client
        self._endpoint = endpoint
        self._model = model

    async def embed(self, text: str) -> Sequence[float]:
        """Return the embedding of ``text`` from the CPU embedding server."""
        url = f"{self._endpoint}{_EMBEDDINGS_PATH}"
        payload = {"model": self._model, "input": text}
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            raw = response.json()["data"][0]["embedding"]
            return [float(value) for value in raw]
        except httpx.HTTPError as err:
            msg = f"embedding request to {url!r} failed"
            raise EmbedderError(msg) from err
        except (KeyError, IndexError, TypeError, ValueError) as err:
            msg = f"malformed embedding response from {url!r}"
            raise EmbedderError(msg) from err
