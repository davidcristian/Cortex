# Runbook for tools over MCP (Slice 6 host half)

Bring up the filesystem MCP server sidecar and validate `McpToolRegistry` against it. CI never
runs any of this (service-free by design, AGENTS.md gate 3): the adapter, the wiring, and the
audit sink are built and 100%-covered without a server. Design: [ADR-0009](../adr/ADR-0009-tools-mcp.md);
module: [brain-tools.md](../modules/brain-tools.md).

## Bring up the filesystem sidecar

The sidecar runs the reference `@modelcontextprotocol/server-filesystem` bridged to
streamable-http by `supergateway`, confined to a **read-only** `/projects` mount. Point it at a
host directory the tool may read (default `./sandbox`):

```
mkdir -p sandbox && echo "hello from the sandbox" > sandbox/hello.txt
CORTEX_TOOLS_ROOT=./sandbox \
  docker compose -f docker-compose.yml -f docker-compose.tools.yml up -d mcp-filesystem
```

- **Sanity poke:** watch `docker compose logs mcp-filesystem` for supergateway's "listening"
  line; the streamable-http endpoint is `http://127.0.0.1:9000/mcp`.
- **From WSL** (automount/interop off): the same drvfs + `DOCKER_CONFIG` one-time steps as the
  [llama.cpp runbook](llamacpp-gpu.md).
- **Pin the server** to a patched version (post-EscapeRoute, CVE-2025-53109/53110):
  `@modelcontextprotocol/server-filesystem@<patched>` in the compose command. The read-only,
  single-directory mount bounds the blast radius regardless (ADR-0009, fork 2).

## Run the tools integration test

```
cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \
  CORTEX_TOOLS_READ_TOOL=read_text_file CORTEX_TOOLS_READ_PATH=/projects/hello.txt \
  uv run pytest -m integration --no-cov packages/tools
```

`--no-cov` matters. The 100% gate in the workspace addopts would otherwise fail the run. This
opens a real streamable-http MCP session, lists the server's tools, and reads a file through
`McpToolRegistry`. CI's fake session cannot prove that behavior. Adjust `CORTEX_TOOLS_READ_TOOL`
if the pinned server names its read tool differently (older builds used `read_file`).

## End-to-end (the cortex actually uses a tool)

With both up, `docker compose -f docker-compose.yml -f docker-compose.tools.yml up` runs the
brain with `CORTEX_TOOLS_BACKEND=mcp`, so a turn that needs a file calls the tool, the dispatch
is audited (one `cortex.tools.audit` line per call), and the result is fed back to the model.
A real model that emits tool calls also needs the GPU compose up with `--jinja` (ADR-0009).

## Teardown

```
docker compose -f docker-compose.yml -f docker-compose.tools.yml down
```
