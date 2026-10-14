# Install the file sidecar's packages at image build

**Status:** open, waiting for its trigger
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-15
**Trigger:** the file sidecar is seen to exit or restart for a reason other than a compose recreate, or a turn is seen served without the file tools while it restarts.

The filesystem sidecar in `docker/docker-compose.tools.yml` runs `npm install -g` for
`supergateway` and the filesystem server every time its container starts. A restart therefore waits
for the install: a container with the same packages committed into its image listened in 0.13 of
the time after `docker restart`, with npm's cache warm in both
([readings](../../readings/tool-sidecar-calls.md#a-request-its-client-abandoned)). The install also
resolves the two packages' transitive dependencies again on every new container, since a global
install reads no lock file.

The one exit seen so far, on a late answer to an abandoned request, is gone since the bridge moved
to 4.1.0, so no restart is known to happen in normal use and the cost has no consumer yet.

## What to do

Build a small image from `node:22-bookworm-slim` with a `package.json` and a committed
`package-lock.json` naming the two exact versions, install with `npm ci` at build time, and point
the compose service at it with the same command minus the install. Check it with the scans every
compose change goes through (`bindcheck`, `volumecheck`, `defaultcheck`), confirm the CI path rules
build it, and measure the restart again against the readings above.

## History

- 2026-10-15: filed when the bridge moved to 4.1.0; the restart cost was measured beside the fix.
