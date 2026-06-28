# syntax=docker/dockerfile:1
# The dockerized Python brain (AGENTS.md: brain in Docker, body on the host).
# Slice 2 ships the seam server only: `python -m cortex_orchestrator` hosting
# BrainService (proto/body.proto). CPU-only image. GPU wiring arrives with the
# docker-compose.gpu.yml override in Slice 4 (docs/ROADMAP.md).
#
# Official uv image pattern: build the venv with uv, ship it on a bare Python base.
# Both stages share the python:3.12-slim-trixie base so the venv transplants cleanly.

FROM ghcr.io/astral-sh/uv:0.11-python3.12-trixie-slim AS builder

# Use the image's interpreter (never a uv-managed download, whose path would not exist
# in the runtime stage), precompile bytecode for fast cold starts, and copy out of the
# cache mount instead of hardlinking across filesystems.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# The whole uv workspace: every member is a path dependency of the virtual root, so a
# deps-first layer split buys little; .dockerignore keeps .venv/tests/caches out.
COPY . .

# Runtime dependencies only (--no-dev); --no-editable installs the workspace packages
# into site-packages so the final image needs the venv alone, not the source tree.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-trixie

# Non-root runtime user; the venv stays root-owned (read-only to the service).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin cortex

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER cortex

# Seam config is env-only (CORTEX_SEAM_HOST/PORT, ADR-0003 d6). The in-process default
# is loopback; Compose sets CORTEX_SEAM_HOST=0.0.0.0 so the published port can reach it.
EXPOSE 50051

CMD ["python", "-m", "cortex_orchestrator"]
