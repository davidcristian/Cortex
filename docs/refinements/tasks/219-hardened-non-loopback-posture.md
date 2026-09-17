# A hardened non-loopback posture

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** ROADMAP assumption 5, the security model in `docs/ROADMAP.md` that says the machine
is single-user with loopback-only listeners and a shared-secret token, being revised to admit a
second user or a body and brain on different machines, or any compose file, runbook or default in
the tree placing a seam listener where a second machine reaches it past the host firewall the body
override relies on. Whether the machine really has one user is not something the tree can hold;
that assumption is where the tree says so.
**Verified:** 2026-09-17

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

The body binds a configurable interface (loopback for dev,
`0.0.0.0` for the container→host path) behind the seam token + host firewall (assumption 5's
revisit). mTLS / per-direction tokens, if the machine ever leaves single-user.

**What would close it, named place by place**, since "mTLS or per-direction tokens" is a posture
rather than a change. Transport credentials reach four places, one per end of each direction, and
one dependency. On the brain to body direction, the brain opens the channel with
`aio.insecure_channel` in `GrpcBodyGateway.connect`
(`brain/packages/body_client/src/cortex_body_client/gateway.py`), which would take channel
credentials and a trust root from configuration, and the body serves `Server::builder()` over a
plain `TcpListenerStream` in the Tauri shell's `body_server::start`, which would take a server TLS
config and, for mutual authentication, a client certificate root. On the body to brain direction,
the brain serves with `server.add_insecure_port` in
`brain/packages/orchestrator/src/cortex_orchestrator/server.py`, and the body dials with
`Channel::from_shared` in `body/crates/rpc/src/client.rs`, which the shell reaches through
`BrainSeamClient::connect_lazy_with_token`. The dependency is the one thing here that
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
- 2026-09-17: read again and unchanged, with two corrections. The body said transport credentials
  reach four places and named two; the other two are the ends of the body to brain direction, the
  brain's `add_insecure_port` and the body's `Channel::from_shared`, and all four are named now. The
  trigger named a fact about the machine that the tree cannot hold, so it now names where the tree
  records that fact, ROADMAP assumption 5, and the deployments that would contradict it. Neither has
  moved: the assumption still reads single-user, the base compose file publishes the brain's port
  on `127.0.0.1` only, and the body override's widened bind still leaves the port to the host
  firewall. The lockfile still pins tonic 0.14.6, and no commit since 2026-09-12 touches the four
  places.
