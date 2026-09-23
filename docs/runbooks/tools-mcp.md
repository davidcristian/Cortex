# Runbook: tools over MCP

Bring up the filesystem MCP server sidecar and check `ReconnectingMcpToolRegistry` against it. CI
never runs any of this, because CI runs no services. Design:
[ADR-0009](../adr/ADR-0009-tools-mcp.md); module contract:
[brain-tools.md](../modules/brain-tools.md).

## Bring up the filesystem sidecar

The sidecar runs the reference `@modelcontextprotocol/server-filesystem` bridged to streamable-http
by `supergateway`, confined to a read-only `/projects` mount. Point it at a host directory the tool
may read (default `./sandbox`):

```
mkdir -p sandbox && echo "hello from the sandbox" > sandbox/hello.txt
CORTEX_TOOLS_ROOT=./sandbox \
  docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml up -d mcp-filesystem
```

Watch `docker compose logs mcp-filesystem` for supergateway's "listening" line; the streamable-http
endpoint is `http://127.0.0.1:9000/mcp`. From WSL with automount and interop off, the same drvfs
and `DOCKER_CONFIG` steps as [llamacpp-gpu.md](llamacpp-gpu.md) apply. The compose command names an
exact server version
(`@modelcontextprotocol/server-filesystem@2026.1.14`, past the EscapeRoute fixes CVE-2025-53109
and CVE-2025-53110 patched in `2025.7.1`), and an exact `supergateway` version too. Change those
deliberately and never float back to unversioned `npx`; the read-only single-directory mount
bounds the damage either way. The container installs both at start rather than running them
through `npx`, and the bridge runs `--stateful`, so expect a slower first boot, which the brain
tolerates because it dials no sidecar at startup.

## What the sidecar costs a turn

The brain opens a fresh MCP session per call, so a turn pays one session open to advertise its
tools before the first token, plus one per dispatched call, and two per call for a subagent. The
open itself is cheap, 17.8 ms against a control server on the FastMCP transport the email sidecar
serves, which is the transport's floor. What is not cheap is what a sidecar does when a session
opens.

| filesystem sidecar configuration | one open | `describe_tools` | one `invoke` |
| --- | --- | --- | --- |
| `npx` per spawn, bridge stateless (before 2026-08-08) | 565 ms | 1156 ms | 1740 ms |
| both binaries installed, bridge `--stateful` (shipped) | 134 ms | 146 ms | 154 ms |
| the same two calls on a session already open | n/a | 4.4 ms | 3.8 ms |

Two faults produced the first row, both in the bridge's stateless mode. It spawned the stdio server
per JSON-RPC request, where `npx` spent about 420 ms resolving the named version again (bare `node`
starts in 18 ms; the installed server answers in 107 ms), and it never reaped those children, so a
few hundred tool calls left 1452 live server processes holding 20.5 GiB. Under `--stateful` one
child serves one MCP session and dies when the client ends it, leaving one process and 110 MiB, and
`--sessionTimeout 60000` reaps an abandoned session. Sixteen concurrent fresh-session
`read_text_file` calls returned in 511 ms with no errors and no child left behind. If you change
the versions or the bridge, re-run the harness below against this table.

## Run the tools integration tests

```
cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \
  CORTEX_TOOLS_READ_TOOL=read_text_file CORTEX_TOOLS_READ_PATH=/projects/hello.txt \
  uv run pytest -m integration --no-cov packages/tools
```

`--no-cov` is required, or the workspace's 100% coverage threshold fails the run. This opens a real
streamable-http MCP session, lists the server's tools, and reads a file through `McpToolRegistry`,
which CI's fake session cannot prove. The same file's second case needs no sidecar: it stands up a
listener that accepts the connection and answers nothing, and asserts that `BoundedToolRegistry`
cuts the call at its bound, that what comes out is a `ToolError` rather than the `ExceptionGroup`
an unclean unwind would raise, and that no client task survives the cut. Adjust
`CORTEX_TOOLS_READ_TOOL` if the server version you named calls its read tool `read_file`.

The harness behind the table above is a second integration test. It asserts how many session opens
each turn shape pays, against the shipped registry stack, and prints what one costs, with a
pre-warmed session as the control so the timings are provably reading the open and not the sidecar:

```
cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \
  uv run pytest -m integration --no-cov -s \
  packages/orchestrator/tests/test_mcp_handshake_live.py
```

`-s` is what prints the numbers. Twenty samples per condition by default
(`CORTEX_TOOLS_HANDSHAKE_SAMPLES`), about 16 s against the shipped sidecar.

## End to end, where the cortex uses a tool

With both up,
`docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml up`
runs the brain with `CORTEX_TOOLS_BACKEND=mcp`, so a turn that needs a file calls the tool, the
dispatch is audited (one `cortex.tools.audit` line per call), and the result is fed back to the
model. That line is a bare `tool.invocation` message followed by its fields, printed in name
order. Which fields it has depends on the call, so it is printed below once per shape, each a line
`brain/packages/tools/tests/test_audit.py` asserts whole against the shipped formatter. In order:
a call that succeeded and was made for no chat, turn or task, every id the dispatch did not have
being left off rather than printed empty; a call that failed, whose `error` stands where
`result_chars` would; a cortex call, with the chat, the turn and the id the model gave the call; a
delegated call, naming the task and the turn that spawned it; and a schedule fire, with the chat
that scheduled the item, the
`item_id` of the item that fired, and no turn.

```text
INFO:cortex.tools.audit:tool.invocation arguments={"path":"<path>"} at=<timestamp> ok=True result_chars=<size of the result> tool=<tool name> trust=untrusted
INFO:cortex.tools.audit:tool.invocation arguments={} at=<timestamp> error="<short detail>" ok=False tool=<tool name> trust=untrusted
INFO:cortex.tools.audit:tool.invocation arguments={} at=<timestamp> call_id=<call id> ok=True result_chars=<size of the result> session_id=<chat id> tool=<tool name> trust=untrusted turn_id=<turn id>
INFO:cortex.tools.audit:tool.invocation arguments={} at=<timestamp> ok=True result_chars=<size of the result> session_id=<chat id> task_id=<task id> tool=<tool name> trust=untrusted turn_id=<turn id>
INFO:cortex.tools.audit:tool.invocation arguments={} at=<timestamp> call_id=schedule-<item id> item_id=<item id> ok=True result_chars=<size of the result> session_id=<chat id> tool=<tool name> trust=untrusted
```

A success logs the size of its result under `result_chars` and never the content; a failure logs
its short detail under `error`; every line has the tool's name, its arguments, the result's `trust`
and the time the dispatch stamped under `at`. The work a call was made for is up to four ids,
`session_id`, `turn_id`, `task_id` and `item_id`, each printed only when the dispatch had it, so
`grep turn_id=` on one id gathers a turn's own tool calls, the tool calls its subagents made, the
line a failed turn wrote, and every line about a handoff that turn asked for, while
a subagent's `task_id` selects one delegate's work out of a batch. None of the four has a prefix,
so grep a field name with an id you already have: the brain mints a turn, a task and an item as a
bare `uuid4` and the overlay mints a chat as a bare `crypto.randomUUID`.

`call_id` is the fifth id and is read differently. It is `ToolCall.id`, the string the result and
its `Role.TOOL` message are keyed by, and on a cortex call it is whatever the model emitted, where
the four work ids come off the dispatch stamp and are the brain's. Read it as what was asked for,
never as an assertion: a `call_id=schedule-...` on a line with no `item_id` is a model that chose
to write the ticker's prefix, not a fire.

One kind of line reads `trust=trusted` beside `ok=False`, and it is not a contradiction. The email
sidecar composes four answers without reading a message (a search the server refused, a folder no
mailbox has, an empty search, and a uid that is not there) and the brain re-stamps each trusted
when its bytes equal the text it holds for it. The first two arrive marked failed. The other two
arrive `ok=True` and are the only successful answers this sidecar gets `trust=trusted` for, and
they are rendered over the `uid` and `folder` the same line prints under `arguments`, which is how
to learn what the model was told when `result_chars` gives only a size. A turn whose remote answers
were all four stays untainted, so a `send_email` after a mistyped search reaches the confirmation
card. One byte of drift in the sidecar's wording puts the answer back on the untrusted side, and
`just check-crosscheck` fails on that drift before it ships.

A real model that emits tool calls also needs the GPU compose up. Validated 2026-07-03: with both
up, a `Converse` turn asking for a file's contents made the resident gemma-4-12B emit
`read_text_file` through the audited loop and answer with the file's exact contents. The override
advertises only the server's read tools (`CORTEX_TOOLS_ALLOW__FILESYSTEM`), since the reference
server also ships write tools the read-only mount would only block with `EROFS`. The mount stays
the security boundary and the allowlist is usability plus defence in depth.

## Keep the audit in a file

The lines above live as long as the container's log driver keeps them. Setting `CORTEX_TOOLS_AUDIT_FILE` to a path makes every dispatcher, the cortex's, the subagents'
and the ticker's, also append one JSON object per call to that file, after writing the log line. It
holds the same fields the line prints and no more: the size of a successful result rather than its
content, every URL credential withheld, and a value the line cuts kept as the line's own cut text.
The base compose file passes it through by name with no value, so it is off unless you set it on
the host.

The brain runs as uid 10001, and the file must be somewhere that user can write and that outlives
the container. A named volume mounted at a path the image does not already have is created owned by
root and every append then fails; mounted over `/home/cortex`, the user's own home, it takes that
directory's owner and works (checked 2026-09-17). So an override file of your own, kept outside
this repo, looks like this:

```yaml
services:
  brain:
    environment:
      CORTEX_TOOLS_AUDIT_FILE: /home/cortex/tools-audit.jsonl
    volumes:
      - cortex-home:/home/cortex
volumes:
  cortex-home:
```

Add it with one more `-f` after the files you already layer, then read it with `jq`:

```bash
docker compose --project-directory . -f docker/docker-compose.yml -f <your override> \
  exec -T brain cat /home/cortex/tools-audit.jsonl | jq -c 'select(.turn_id == "<turn id>")'
```

`select(.task_id == "<task id>")` gives one delegate's calls and `select(.ok == false)` every
failed one. Test `.arguments | type` before reading into it: it is `"object"` when the line
printed the arguments whole and `"string"` when it cut them.

A record that could not be appended is on the log line all the same, followed by a
`cortex_tools.audit_file` warning, `tool.audit.gap`, whose `error` says why, with `path` and `tool`
beside it. A file with gaps is incomplete rather than wrong, and the log lines of that period are
the complete record.

Nothing rotates or deletes the file. The sink opens it again for every record, so rotating is a
`mv`, or `logrotate` without `copytruncate`, and the next call creates a fresh file with mode
`0600`. A record torn by a full disk stays on its own line, and `jq -R 'fromjson? // empty'` reads
past such a line where plain `jq` stops.

## Both tool families at once

Layer the email override on top and the brain aggregates the two sidecars behind one registry.
Each override contributes its own `CORTEX_TOOLS_ENDPOINTS__<name>` env key, so the compose merge
keeps both:

```
set -a; . ~/.cortex/email.env; set +a
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.tools.yml -f docker/docker-compose.email.yml up
```

One turn can then read a file and search the mailbox, and every call still flows through the same
audited dispatcher. A sidecar that is down fails tool listing loudly, as a `ToolError` that
becomes an `is_error` result the model sees, rather than silently shrinking the tool set. To keep
the healthy sidecars serving instead, set `CORTEX_TOOLS_ON_UNAVAILABLE=skip`: the dead sidecar's
tools drop out of the advertisement and every walk logs a `tool sidecar unavailable` warning
naming it. Sessions are opened per call, so skip mode covers a sidecar down at any time, including
at boot, and a recovered sidecar rejoins on its next call with no brain restart.

A sidecar that is down is refused at the dial. A sidecar that is hung, accepting the call and never
answering, raises nothing at all, since the MCP session's own wait for a response is unbounded.
Every endpoint is therefore wrapped innermost in a `BoundedToolRegistry`, so a call that outruns
`CORTEX_TOOLS_CALL_TIMEOUT_S` (default `60.0`, seconds, covering a listing and an invoke alike) is
cancelled and reported as the same `ToolError` a refused sidecar raises: the model is handed an
`is_error` result naming the tool and the bound, the dispatch is audited like any other, and under
`skip` a bounded listing drops that sidecar out of the advertisement exactly as a dead one does.
The number is far past a healthy call, which the table above measures at 154 ms; a value at or
below zero fails the brain at boot. Only the sidecars are bounded, never the built-in tools beside
them, since a delegated batch and a confirmation waiting on a human are supposed to take a while.

**A whole delegated dispatch has to fit inside the run that contains it.** A subagent's whole run
is bounded by
`CORTEX_SUBAGENTS_RUN_TIMEOUT_S` (default 2400 s) and that deadline covers the tool dispatches its
loop makes, so with the two settings the wrong way round the run's deadline fires: the whole
delegated run is lost rather than the one call, it comes back with no text, and the refusal the
cortex reads says the subtask would not stop talking, which points at the model instead of at the
sidecar. What has to fit is the dispatch rather than the bound, because a dispatch spends the bound
more than once: the run lists its tools before its rounds, `ConfirmFreeToolRegistry` lists them again
on every delegated dispatch, an aggregate over several sidecars lists them a third time to route,
and then the call itself runs. So one wedged sidecar costs a delegated dispatch three bounds with
one sidecar configured and seven with two, and `CORTEX_TOOLS_CALL_TIMEOUT_S=700` under a 900 s run
reads as ordered and is not. The brain therefore fails to start when that product is not strictly
under `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` and both capabilities are on, naming both settings, both
values, the multiple and the product. Lower the call bound or raise the run bound; the shipped pair
already clears by a factor of thirteen with one sidecar and five with two. With either capability
off nothing is checked, and a run that dispatches many times can still spend its whole deadline on
a broken sidecar, which is a slow turn rather than a misdiagnosed one.

A turn that repeats one call has it dispatched at most twice, and at most once per inference round
(`CORTEX_TOOLS_SALIENCE`, default `repeat`). The refusal is audited like any other dispatch, so the
brain's logs show the repeat as a `tool.invoke` line whose detail is the refusal rather than a
second sidecar call, and the sidecar sees nothing. Set `CORTEX_TOOLS_SALIENCE=off` to restore the
unfiltered loop. To retune the across-loop cap rather than remove it, set
`CORTEX_TOOLS_SALIENCE_LIMIT` (default 2): `1` refuses the second dispatch too, a larger number
allows more, and the once-per-round clause is absolute either way. A value below 1 fails the brain
at boot, and the number does nothing while `CORTEX_TOOLS_SALIENCE=off`.

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.tools.yml down
```
