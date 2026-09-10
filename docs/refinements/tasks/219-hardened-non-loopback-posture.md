# A hardened non-loopback posture

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** The machine leaving single-user, which is what mTLS or per-direction tokens wait on.
**Verified:** 2026-09-10

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

The body binds a configurable interface (loopback for dev,
`0.0.0.0` for the container→host path) behind the seam token + host firewall (assumption 5's
revisit). mTLS / per-direction tokens, if the machine ever leaves single-user.

## Trail

- 2026-09-10: read against the tree and not fired. The machine is still single-user, so the
  condition the entry waits on has not arrived. The posture it describes is also still the posture
  the code has: the shell binds `CORTEX_BODY_ADDR`, defaulting to `127.0.0.1:50151` and documented
  in `docker/docker-compose.body.yml` as the setting an operator widens to `0.0.0.0:50151` for the
  container to reach it, and the only authentication in front of that socket is
  `SeamTokenValidator`, one shared `x-cortex-seam-token` compared in constant time and passing
  everything through when the configured token is empty. There is no TLS on either direction of
  this seam and no per-direction token, which is what this entry is for.
