"""The part of a text the embedder is given: a prefix the embedding model's context always holds."""

# The input bound of nomic-embed-text-v1.5 under the memory stack's llama-server, which counts the
# model's own start and end tokens against it.
EMBEDDER_CONTEXT_TOKENS = 2048

# The model's tokenizer measured at most one token per character over prose, code and non-Latin
# text (docs/readings/embedding-input.md), so this leaves about a tenth of the context spare.
EMBED_INPUT_CHARS = 1800


def embedding_input(text: str) -> str:
    """Return the first ``EMBED_INPUT_CHARS`` characters of ``text``, or all of a shorter one."""
    return text[:EMBED_INPUT_CHARS]
