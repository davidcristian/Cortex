"""LlamaCppEmbedder: the Embedder port over a llama-server OpenAI /v1/embeddings endpoint."""

from collections.abc import Sequence

import httpx

from cortex_core import EmbedderError, EmbedRole

_EMBEDDINGS_PATH = "/v1/embeddings"

_DEFAULT_EMBED_MODEL = "embedding"

# The query prefix the card of nomic-embed-text-v1.5, the shipped embedding model, asks for.
DEFAULT_QUERY_PREFIX = "search_query: "


class LlamaCppEmbedder:
    """Embedder over a CPU llama-server's OpenAI-compatible embeddings endpoint."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        endpoint: str,
        *,
        model: str = _DEFAULT_EMBED_MODEL,
        query_prefix: str = DEFAULT_QUERY_PREFIX,
    ) -> None:
        self._client = http_client
        self._endpoint = endpoint
        self._model = model
        self._query_prefix = query_prefix

    async def embed(self, text: str, *, role: EmbedRole = EmbedRole.DOCUMENT) -> Sequence[float]:
        """Return the embedding of ``text``, sent after the query prefix when it is a query."""
        url = f"{self._endpoint}{_EMBEDDINGS_PATH}"
        sent = self._query_prefix + text if role is EmbedRole.QUERY else text
        payload = {"model": self._model, "input": sent}
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
