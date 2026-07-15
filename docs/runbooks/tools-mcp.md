# Runbook for tools over MCP (Slice 6 host half)

Bring up the filesystem MCP server sidecar and validate `ReconnectingMcpToolRegistry` against it. CI never
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
  docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml up -d mcp-filesystem
```

- **Sanity poke:** watch `docker compose logs mcp-filesystem` for supergateway's "listening"
  line; the streamable-http endpoint is `http://127.0.0.1:9000/mcp`.
- **From WSL** (automount/interop off): the same drvfs + `DOCKER_CONFIG` one-time steps as the
  [llama.cpp runbook](llamacpp-gpu.md).
- **The server is version-pinned in the compose command**
  (`@modelcontextprotocol/server-filesystem@2026.1.14`, past the EscapeRoute fixes
  CVE-2025-53109/53110 patched in `2025.7.1`; the `supergateway` bridge is pinned too). Bump
  the pins deliberately. Never float back to unversioned `npx`. The read-only,
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

With both up, `docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml up` runs the
brain with `CORTEX_TOOLS_BACKEND=mcp`, so a turn that needs a file calls the tool, the dispatch
is audited (one `cortex.tools.audit` line per call), and the result is fed back to the model.
A real model that emits tool calls also needs the GPU compose up (`--jinja` is baked into its
command). Validated 2026-07-03: with both up, a `Converse` turn asking for a file's contents made
the resident gemma-4-12B natively emit `read_text_file` through the audited loop and answer with
the file's exact contents (ADR-0009 addendum).

The override advertises only the server's **read** tools (`CORTEX_TOOLS_ALLOW__FILESYSTEM`,
ADR-0009 refinements addendum): the reference server also ships write tools the read-only
mount would only `EROFS`-block, and there is no point showing the model a tool that cannot
work. The mount stays the security boundary; the allowlist is UX plus defense in depth. If a
pin bump renames tools, update that allowlist alongside it.

## Both tool families at once (filesystem + email)

Layer the email override on top and the brain aggregates the two sidecars behind one registry
(ADR-0009 refinements addendum). Each override contributes its own
`CORTEX_TOOLS_ENDPOINTS__<name>` env key, so the compose merge keeps both:

```
set -a; . ~/.cortex/email.env; set +a
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.tools.yml -f docker/docker-compose.email.yml up
```

One turn can then read a file **and** search the mailbox; every call still flows through the
same audited dispatcher. A sidecar that is down fails tool listing loudly (`ToolError` → an
`is_error` result the model sees) rather than silently shrinking the tool set. To keep the
healthy sidecars serving instead, set `CORTEX_TOOLS_ON_UNAVAILABLE=skip` (ADR-0009
degraded-mode addendum): the dead sidecar's tools drop out of the advertisement and every
walk logs a `tool sidecar unavailable` warning naming it and stays degraded, never silent. Sessions
are now opened **per call** (`ReconnectingMcpToolRegistry`, ADR-0009 boot-tolerance addendum),
so skip mode covers a sidecar down at *any* time, including one down when the brain **boots**
(startup no longer fails). A recovered sidecar rejoins on its next call, **no brain
restart needed**.

A turn that repeats one call has it dispatched at most twice, and at most once per inference
round (`CORTEX_TOOLS_SALIENCE`, default `repeat`, ADR-0009 salience addendum). The refusal is
audited like any other dispatch, so the brain's logs show the repeat as a `tool.invoke` line
whose detail is the refusal rather than a second sidecar call, and the sidecar sees nothing.
Set `CORTEX_TOOLS_SALIENCE=off` to restore the unfiltered loop when comparing behavior.

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml down
```
