# A hardened non-loopback posture

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** The machine leaving single-user, which is what mTLS or per-direction tokens wait on.

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

The body binds a configurable interface (loopback for dev,
`0.0.0.0` for the container→host path) behind the seam token + host firewall (assumption 5's
revisit). mTLS / per-direction tokens, if the machine ever leaves single-user.
