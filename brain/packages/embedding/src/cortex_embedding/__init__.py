"""llama.cpp CPU adapter for the core's Embedder port (docs/modules/brain-embedding.md)."""

from cortex_embedding.embedder import DEFAULT_QUERY_PREFIX, LlamaCppEmbedder

__all__ = ["DEFAULT_QUERY_PREFIX", "LlamaCppEmbedder"]
