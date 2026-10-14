# A cancelled call takes the file sidecar down

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-15

On the Linux shell, Stop ended a turn whose tool listing waited on a frozen file sidecar. When the
sidecar was thawed, its child answered the cancelled session's `initialize`, and `supergateway`
3.4.3 exited on `No connection established for request ID: 0` from the MCP SDK's
`webStandardStreamableHttp.js`. Compose restarted the container, which runs `npm install` again
before it listens, and a turn sent 3 s after the thaw was served without the file tools
([readings](../../readings/overlay-interruption-flows.md#stop-while-a-tool-listing-hangs)).

Only the frozen case was seen. The same exit should follow any request the brain stops waiting on
before the child answers, such as a call cut by `CORTEX_TOOLS_CALL_TIMEOUT_S`; that is an
assumption until a row shows it.

## Reproduce

On the stack with `docker/docker-compose.tools.yml`, `docker pause` the `mcp-filesystem`
container, ask the overlay to list your files, press Stop, `docker unpause` it, and read
`docker logs` of the sidecar: the exit and a fresh `npm install` follow.

## What to do

First a row without a pause: a slow call cut by a short `CORTEX_TOOLS_CALL_TIMEOUT_S`, to learn
whether a normal cancel exits the gateway too. Then check whether a later `supergateway` release
handles a late answer for a closed request, and whether installing both packages into an image at
build time makes the restart short. A change to the sidecar's command or image is checked by
`bindcheck` and `volumecheck` like any compose change.

## History

- 2026-10-15: filed from the interruption flows on the Linux shell.
