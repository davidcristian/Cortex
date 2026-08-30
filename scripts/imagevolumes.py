"""What each image a compose file names declares as a VOLUME, recorded so the check can read it."""

from typing import NamedTuple


class Row(NamedTuple):
    """One image as docker reported it: what it declares, and what it would declare in a child."""

    volumes: tuple[str, ...]
    onbuild: tuple[str, ...]


# What docker reported for each image: what it declares itself, and what its ONBUILD triggers
# would declare in a child. First measured on 2026-08-25, re-measured on 2026-08-30.
# Regenerate with `just image-volumes`.
IMAGE_VOLUMES: dict[str, Row] = {
    "dovecot/dovecot:2.3.21": Row(("/etc/dovecot", "/srv/mail"), ()),
    "pgvector/pgvector:pg16": Row(("/var/lib/postgresql/data",), ()),
    "ghcr.io/ggml-org/llama.cpp:server": Row((), ()),
    "node:22-bookworm-slim": Row((), ()),
    "redis:8-alpine": Row((), ()),
    "cortex-brain": Row((), ()),
    "cortex-mcp-email": Row((), ()),
    "cortex-model-host": Row((), ()),
    # The two bases the rows above are built on, first measured on 2026-08-28.
    "python:3.12-slim-trixie": Row((), ()),
    "ghcr.io/ggml-org/llama.cpp:server-cuda": Row((), ()),
}

RECORD_PATH = "scripts/imagevolumes.py"
