# syntax=docker/dockerfile:1
# The dockerized Python brain, which runs `python -m cortex_orchestrator`. Both stages share the
# python:3.12-slim-trixie base, so the virtual environment uv builds in the first stage runs
# unchanged in the second.

FROM ghcr.io/astral-sh/uv:0.11-python3.12-trixie-slim AS builder

# Use the image's own interpreter, never a uv-managed download whose path the runtime stage does
# not have. Precompile bytecode for a fast cold start, and copy out of the cache mount rather than
# hardlink across filesystems.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# The whole uv workspace: every member is a path dependency of the root, so a dependencies-first
# layer split buys little. .dockerignore keeps .venv, tests and caches out.
COPY . .

# Runtime dependencies only, and --no-editable installs the workspace packages into site-packages
# so the final image needs the virtual environment alone and not the source tree.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-trixie

# Non-root runtime user; the virtual environment stays root-owned and read-only to the service.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin cortex

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER cortex

# The gRPC server is configured from the environment only. Its in-process default binds loopback,
# and Compose sets CORTEX_SEAM_HOST=0.0.0.0 so the published port can reach it.
EXPOSE 50051

CMD ["python", "-m", "cortex_orchestrator"]
