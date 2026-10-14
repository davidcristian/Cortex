# Readings: tool sidecar calls

What one MCP call to a tool sidecar costs, and how the call bound behaves against a real socket.
Cited by [ADR-0009](../adr/ADR-0009-tools-mcp.md), decisions 5, 9, 10 and 19. The
[tools runbook](../runbooks/tools-mcp.md) quotes the per-call table for operators.

## One session open

**2026-08-08.** Opening a fresh session against a control server on the FastMCP streamable-http
transport the email sidecar serves (two trivial tools, nothing done on connect) took **17.8 ms**
(n=30, 16.5 to 21.5 ms), about 0.4% of a recalling turn's time to first token on the same machine.
A fresh session's `invoke` issues three JSON-RPC calls (`initialize`, `tools/call`, and the
`tools/list` the SDK's `call_tool` makes to cache output schemas) and `describe_tools` issues two.

Method: a wrapping opener timing `streamable_http_session` against the control server, and
`orchestrator/tests/test_mcp_handshake_live.py` counting opens per turn through the shipped stack.

## The filesystem sidecar, before and after the bridge fix

**2026-08-08.** Against the version-locked filesystem sidecar, with the bridge spawning `npx` per
request and then with both packages installed at start and the bridge `--stateful`:

| configuration | one open | pre-token walk | one dispatch |
| --- | --- | --- | --- |
| `npx` per spawn, bridge stateless | 565 ms | 1156 ms | 1740 ms |
| version-locked binaries, bridge `--stateful` (shipped) | 134 ms | 146 ms | 154 ms |
| the same calls on a session already open | n/a | 4.4 ms | 3.8 ms |

Each JSON-RPC round trip took 3 to 5 ms; the rest was the bridge's child spawn, about 420 ms of it
`npx` resolving the package again. The stateless bridge also never reaped its children: a few
hundred calls left 1452 server processes; after the fix the same run left one. With the fix, each
call still pays about 125 ms of child spawn, which only a held session would remove.

Method: every HTTP request traced while the tools integration test and repeated describes and
invokes ran against `docker/docker-compose.tools.yml`; process count from `ps` in the container.

## The call bound against a listener that never answers

**2026-08-21.** With a 1.5 s bound, both verbs raised `ToolError` at 1.50 s and 1.51 s through the
shipped registry stack, and afterwards no client task and no socket survived; only the fake
server's own handler task was alive.

Method: the integration-marked case in `brain/packages/tools/tests` that stands up a TCP listener
accepting the connection and sending nothing.

## A request its client abandoned

**2026-10-15.** The shipped registry stack (`BoundedToolRegistry` over
`ReconnectingMcpToolRegistry`), run from a host script, cut calls to the filesystem sidecar, and the
sidecar's restart count was read after each cut:

| cut | `supergateway` 3.4.3 | 4.1.0 |
| --- | --- | --- |
| `search_files` over 80,000 empty files, bound 1 s (uncut, about 6.5 times the bound) | stayed up | stayed up |
| the same call bound at 0.05, 0.15 and 0.3 s, in or just after the session open | stayed up | not run |
| `list_directory`, 30 cuts at bounds from 0.003 to 0.03 s | stayed up | not run |
| container paused, `list_directory` cut at 2 s, thawed 1 s later | exited, code 1 | stayed up, 3 of 3 |

Without a pause the gateway sends the response headers, session id included, as soon as a request
arrives, and its log shows each cut session closed by the client's `DELETE` before the child's late
answer, which is then dropped. A paused gateway never sent those headers, so the client had no id to
end the session with. On the thaw 3.4.3 sends the answer to a closed stream, nothing catches the
rejection, and the process exits on `No connection established for request ID: 0`; 4.1.0 logs
`Failed to send to StreamableHttp`, and a call 3 s after the thaw was answered each time. On the
live stack under 4.1.0 the overlay flow in [the interruption
flows](overlay-interruption-flows.md#stop-while-a-tool-listing-hangs) kept the sidecar up.

The handshake harness (`orchestrator/tests/test_mcp_handshake_live.py`), run twice against each
version side by side, put 4.1.0 at 0.98 to 1.01 of 3.4.3 on every condition. A restart pays the
`npm install` at start: with npm's cache warm in the container layer, a container with the same
packages committed into its image listened in 0.13 of the time after `docker restart` (three
restarts each). With the container's network disconnected, the install-at-start container still
restarted, from that cache.

Method: `docker run` probes of each version on their own ports beside the stack, `timeout` around
each row, `docker pause` and `unpause`, `docker inspect` for the restart count, and `docker commit`
of a probe for the preinstalled case.

## A mislabeled picture at the engine

**2026-09-19.** llama.cpp build 10680 on the CPU with gemma-4-E2B and its projector, asked the colour
of six single-colour pictures sent as `data:` URIs, four of them under another format's mime type,
answered all six correctly and logged nothing about the label.

Method: a hand-run request per picture against the cached CPU server image.
