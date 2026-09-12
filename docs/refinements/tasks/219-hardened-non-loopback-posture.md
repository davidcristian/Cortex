# A hardened non-loopback posture

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** The machine leaving single-user, which is what mTLS or per-direction tokens wait on.
**Verified:** 2026-09-12

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

The body binds a configurable interface (loopback for dev,
`0.0.0.0` for the container→host path) behind the seam token + host firewall (assumption 5's
revisit). mTLS / per-direction tokens, if the machine ever leaves single-user.

**What would close it, named place by place**, since "mTLS or per-direction tokens" is a posture
rather than a change. Transport credentials reach four places and one dependency. The brain opens
the channel with `aio.insecure_channel` in `GrpcBodyGateway.connect`, which would take channel
credentials and a trust root from configuration. The body serves `Server::builder()` over a plain
`TcpListenerStream` in the Tauri shell's `body_server::start`, which would take a server TLS config
and, for mutual authentication, a client certificate root. The dependency is the one thing here that
is not a line of code: `body/Cargo.toml` pins `tonic = "0.14"` with default features, and tonic
0.14.6's defaults are `router`, `transport` and `codegen`, so no TLS is compiled into this tree at
all and one of the `tls-ring` or `tls-aws-lc` features has to be enabled first. Splitting the one
shared secret into a per-direction pair is separate and cheaper: `CORTEX_SEAM_TOKEN` is read by the
brain's interceptor and by `SeamTokenValidator` for both directions, so a second variable means two
readers, two settings tables and the compose override's own sentence about the token being shared.
The certificate lifecycle, not the code, is what makes this wait on the trigger: a single-user
machine has nowhere to put a private certificate authority that the host firewall does not already
cover.

## Trail

- 2026-09-10: read against the tree and not fired. The machine is still single-user, so the
  condition the entry waits on has not arrived. The posture it describes is also still the posture
  the code has: the shell binds `CORTEX_BODY_ADDR`, defaulting to `127.0.0.1:50151` and documented
  in `docker/docker-compose.body.yml` as the setting an operator widens to `0.0.0.0:50151` for the
  container to reach it, and the only authentication in front of that socket is
  `SeamTokenValidator`, one shared `x-cortex-seam-token` compared in constant time and passing
  everything through when the configured token is empty. There is no TLS on either direction of
  this seam and no per-direction token, which is what this entry is for.
- 2026-09-12: read again and unchanged, and the entry now names the places rather than the posture.
  The brain's half is `aio.insecure_channel` in `GrpcBodyGateway.connect` and the body's is
  `Server::builder()` over a plain `TcpListenerStream` in `body_server::start`, with one shared
  `CORTEX_SEAM_TOKEN` read by both directions in front of them. The reading worth recording is the
  dependency: `body/Cargo.toml` pins `tonic = "0.14"` with default features, and tonic 0.14.6
  declares `default = ["router", "transport", "codegen"]`, so this tree compiles no TLS at all and
  enabling `tls-ring` or `tls-aws-lc` is the first step of any mTLS close, not a detail of it. Still
  not fired: the machine is single-user.
