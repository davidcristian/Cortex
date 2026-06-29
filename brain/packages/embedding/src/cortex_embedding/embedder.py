"""LlamaCppEmbedder: the Embedder port over a llama-server OpenAI /v1/embeddings endpoint."""

from collections.abc import Sequence

import httpx

from cortex_core import EmbedderError

_EMBEDDINGS_PATH = "/v1/embeddings"

# llama-server embeds with whatever model it was started with and ignores this value, but
# the OpenAI schema requires the field; the composition root sets the logical id (ADR-0004).
_DEFAULT_EMBED_MODEL = "embedding"


class LlamaCppEmbedder:
    """Embedder over a CPU llama-server's OpenAI-compatible embeddings endpoint (ADR-0008)."""

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
