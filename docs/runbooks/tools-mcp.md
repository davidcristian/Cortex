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
- **The container installs both pins at start rather than running them through `npx`, and the
  bridge runs `--stateful`.** Expect a slower first boot (an `npm install -g` before it listens),
  which the brain tolerates because it dials no sidecar at startup. Both were measured on
  2026-08-08 and both matter on the turn's critical path; the section below has the numbers.

## What the sidecar costs a turn

The brain opens a **fresh MCP session per call** (ADR-0009 boot-tolerance addendum), so a turn
pays one session open to advertise its tools before the first token, plus one per dispatched call
(two per call for a subagent, whose `UngatedToolRegistry` re-lists before delegating). The open
itself is cheap, 17.8 ms against a control server on the FastMCP transport the email sidecar
serves, which is the transport's floor: what the client and the protocol cost when nothing happens
server-side on connect. What is not cheap is what a sidecar *does* when a session opens, and the
bridge in front of the reference filesystem server used to do the worst possible thing.

| filesystem sidecar configuration | one open | `describe_tools` | one `invoke` |
| --- | --- | --- | --- |
| `npx` per spawn, bridge stateless (before 2026-08-08) | 565 ms | 1156 ms | 1740 ms |
| pinned binaries installed, bridge `--stateful` (shipped) | 134 ms | 146 ms | 154 ms |
| the same two calls on a session already open | n/a | 4.4 ms | 3.8 ms |

Two separate faults, both in the bridge's stateless mode. It spawned the stdio server **per
JSON-RPC request**, and `npx` spent about 420 ms of each spawn re-resolving the pinned package
(bare `node` starts in 18 ms; the installed server answers in 107 ms). And it never reaped those
children: a few hundred tool calls left **1452 live server processes holding 20.5 GiB**. Under
`--stateful` one child serves one MCP session and dies when the client ends it, so the same run
leaves one process and 110 MiB, and `--sessionTimeout 60000` reaps a session abandoned without
that goodbye (verified: eight abandoned children, all gone after the idle window). Concurrency is
the thing `--stateful` could plausibly have broken, since sessions now share a map on the bridge,
so it was checked: sixteen concurrent fresh-session `read_text_file` calls returned in 511 ms with
no errors, no crossed content, and no child left behind.

If you bump the pins or change the bridge, re-run the harness below and compare against this
table. A regression here is invisible in every test that does not time itself.

## Run the tools integration tests

```
cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \
  CORTEX_TOOLS_READ_TOOL=read_text_file CORTEX_TOOLS_READ_PATH=/projects/hello.txt \
  uv run pytest -m integration --no-cov packages/tools
```

`--no-cov` matters. The 100% gate in the workspace addopts would otherwise fail the run. This
opens a real streamable-http MCP session, lists the server's tools, and reads a file through
`McpToolRegistry`. CI's fake session cannot prove that behavior. The same file's second case needs
no sidecar at all: it stands up a listener that accepts the connection and answers nothing, and
asserts that `BoundedToolRegistry` cuts the call at its bound, that what comes out is a `ToolError`
rather than the `ExceptionGroup` or bare `CancelledError` an unclean unwind through anyio's task
group would raise, and that no client task survives the cut. Adjust `CORTEX_TOOLS_READ_TOOL`
if the pinned server names its read tool differently (older builds used `read_file`).

The harness behind the table above is a second integration test. It asserts how many session
opens each turn shape pays (exactly, against the shipped registry stack) and prints what one
costs, with a pre-warmed session as the control arm so the timings are provably reading the open
and not the sidecar:

```
cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \
  uv run pytest -m integration --no-cov -s \
  packages/orchestrator/tests/test_mcp_handshake_live.py
```

`-s` is what surfaces the numbers; without it only the assertions run. Twenty samples per arm by
default (`CORTEX_TOOLS_HANDSHAKE_SAMPLES`), about 16 s against the shipped sidecar.

## End-to-end (the cortex actually uses a tool)

With both up, `docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml up` runs the
brain with `CORTEX_TOOLS_BACKEND=mcp`, so a turn that needs a file calls the tool, the dispatch
is audited (one `cortex.tools.audit` line per call), and the result is fed back to the model.
That line is a bare `tool.invocation` message followed by its fields, the tool's name, `ok`, the
arguments, the result's `trust`, either `result_chars` or `error`, the work the call was made
for, and which call it was, printed in name order by the
formatter the process entry installs (ADR-0038 rendered-fields addendum). The work is up to four
ids (ADR-0009 named-work and named-call addenda): `session_id`, `turn_id`, `task_id` and
`item_id`, each printed only when
the dispatch had it, so `grep turn_id=t-...` gathers a turn's own tool calls, the tool calls its
subagents made, the line a failed turn wrote, and every line about a handoff that turn asked for
(a handoff id is the escalating turn's id, and the swap path spells it under this same name,
ADR-0009 sixth-name addendum), while a subagent's `task_id` selects one
delegate's work out of a batch. A schedule fire carries the chat that scheduled the item, the
`item_id` of the item that fired, and no
turn, because nothing conversational is waiting on it.

`call_id` is the fifth id and is read differently from the other four. It is `ToolCall.id`, the
string the result and its `Role.TOOL` message are keyed by, so it says which of a turn's
dispatches a line is; and on a cortex call it is whatever the model emitted, exactly like `tool`
and `arguments`, where the four work ids come off the dispatch stamp and are the brain's. Read it
as what was asked for, never as an assertion: a `call_id=schedule-...` on a line with no `item_id`
is a model that chose to spell the ticker's prefix, not a fire. It cannot damage the line either
way, the formatter quoting and escaping any value that carries whitespace or a quote and cutting
one past `VALUE_CHARS`, so an id can fill a field and never add one. It used to carry a JSON
copy of the same fields inside the message, which is what the trail needed back when the shipped
handler printed no field at all; see [local-dev-wsl.md](local-dev-wsl.md) for how a line reads
now and what it withholds.
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

A sidecar that is **down** is refused at the dial, which is what `skip` above serves around. A
sidecar that is **hung**, accepting the call and never answering, raises nothing at all: the MCP
session's own wait for a response is unbounded, so before this it held the turn open indefinitely
and nothing above it could tell. Every endpoint is now wrapped innermost in a
`BoundedToolRegistry` (ADR-0009 bound addendum), so a call that outruns
`CORTEX_TOOLS_CALL_TIMEOUT_S` (default `60.0`, seconds, covering a listing and an invoke alike) is
cancelled and reported as the same `ToolError` a refused sidecar raises: the model is handed an
`is_error` result naming the tool and the bound, the dispatch is audited like any other, and under
`skip` a bounded *listing* drops that sidecar out of the advertisement exactly as a dead one does.
The number is deliberately far past a healthy call (the table above measures a fresh-session
`invoke` at 154 ms) and far short of forever; a value at or below zero fails the brain at boot.
Only the sidecars are bounded, never the built-in tools beside them: a delegated batch and a
confirm card waiting on a human are supposed to take a while.

**A whole delegated dispatch has to fit inside the run that contains it.** A subagent's whole run
is bounded by `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` (default 2400 s) and that deadline covers the tool
dispatches its loop makes, so with the knobs set the wrong way round the run's deadline is what
fires: the whole delegated run is lost rather than the one call, it comes back with no text at all,
and the refusal the cortex reads says the subtask would not stop talking, which points at the model
instead of at the sidecar.

What has to fit is the **dispatch** and not the bound, because a dispatch spends the bound more
than once. The run lists its tools before its rounds, `UngatedToolRegistry` lists them again on
every delegated dispatch to strip gated names, an aggregate over several sidecars lists them a
third time to route, and then the call itself runs, and each of those reaches the bound
separately. So one wedged sidecar costs a delegated dispatch **three** bounds with one sidecar
configured and **seven** with two, and `CORTEX_TOOLS_CALL_TIMEOUT_S=700` under a 900 s run reads
as ordered and is not.

The brain therefore **refuses to start** when that product is not strictly under
`CORTEX_SUBAGENTS_RUN_TIMEOUT_S` and both capabilities are on, naming both knobs, both values, the
multiple and the product (ADR-0009 ordering addendum). Lower the call bound or raise the run bound;
the shipped pair already clears by a factor of thirteen with one sidecar and five with two. With
either capability off there is nothing to order, so nothing is checked: without `mcp` no bound is
spent, and a cortex turn announces no deadline for its own calls to sit under. What a passing check
buys is that the first wedged dispatch reaches the model as an error it can act on; a run that
dispatches many times can still spend its whole deadline on a broken sidecar, which is a slow turn
rather than a mis-diagnosed one.

A turn that repeats one call has it dispatched at most twice, and at most once per inference
round (`CORTEX_TOOLS_SALIENCE`, default `repeat`, ADR-0009 salience addendum). The refusal is
audited like any other dispatch, so the brain's logs show the repeat as a `tool.invoke` line
whose detail is the refusal rather than a second sidecar call, and the sidecar sees nothing.
Set `CORTEX_TOOLS_SALIENCE=off` to restore the unfiltered loop when comparing behavior. To retune
the across-loop cap rather than remove it, set `CORTEX_TOOLS_SALIENCE_LIMIT` (default 2): `1`
refuses the second dispatch too, a larger number allows more, and the once-per-round clause is
absolute either way. A value below 1 fails the brain at boot rather than quietly refusing every
call, and the number is inert while `CORTEX_TOOLS_SALIENCE=off`.

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml down
```
