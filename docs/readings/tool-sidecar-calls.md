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

## A mislabeled picture at the engine

**2026-09-19.** llama.cpp build 10680 on the CPU with gemma-4-E2B and its projector, asked the colour
of six single-colour pictures sent as `data:` URIs, four of them under another format's mime type,
answered all six correctly and logged nothing about the label.

Method: a hand-run request per picture against the cached CPU server image.
