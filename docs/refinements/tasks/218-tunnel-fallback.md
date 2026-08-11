# Q3 body-initiated-stream tunnel fallback

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** `host.docker.internal` proving brittle on WSL2.

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

The brain dials the body directly today; if
`host.docker.internal` proves brittle on WSL2, tunneling body-directed calls over a
body-initiated bidi stream is a different `BodyGateway` adapter, with no core/tool/proto change.
