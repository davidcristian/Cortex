# A hardened non-loopback posture

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** ROADMAP assumption 5, the security model in `docs/ROADMAP.md` that says the machine
is single-user with loopback-only listeners and a shared-secret token, being revised to admit a
second user or a body and brain on different machines; or any compose file, runbook or default in
the tree putting a listener where a second machine reaches it past the host firewall the body
override relies on. Whether the machine really has one user is not something the tree can record;
that assumption is where the tree says so.
**Verified:** 2026-09-17

The body binds a configurable interface, loopback for development and `0.0.0.0` for the
container-to-host path, behind the shared token and the host firewall. mTLS or per-direction tokens
would be wanted if the machine ever stops being single-user.

Transport credentials reach four places, one per end of each direction, plus one dependency. On the
brain-to-body direction, the brain opens the channel with `aio.insecure_channel` in
`GrpcBodyGateway.connect` (`brain/packages/body_client/src/cortex_body_client/gateway.py`), which
would take channel credentials and a trust root from configuration, and the body serves
`Server::builder()` over a plain `TcpListenerStream` in the Tauri shell's `body_server::start`,
which would take a server TLS config and, for mutual authentication, a client certificate root. On
the body-to-brain direction, the brain serves with `server.add_insecure_port` in
`brain/packages/orchestrator/src/cortex_orchestrator/server.py`, and the body dials with
`Channel::from_shared` in `body/crates/rpc/src/client.rs`, which the shell reaches through
`BrainRpcClient::connect_lazy_with_token`.

The dependency is the one thing here that is not a line of code: `body/Cargo.toml` declares
`tonic = "0.14"` with default features, and tonic 0.14.6's defaults are `router`, `transport` and
`codegen`, so no TLS is compiled into this tree at all and one of the `tls-ring` or `tls-aws-lc`
features has to be enabled first.

Splitting the one shared secret into a per-direction pair is separate and cheaper:
`CORTEX_SEAM_TOKEN` is read by the brain's interceptor and by `RpcTokenValidator` for both
directions, so a second variable means two readers, two settings tables and a change to the compose
override's sentence about the token being shared.

The certificate lifecycle, not the code, is what makes this wait: a single-user machine has nowhere
to put a private certificate authority that the host firewall does not already cover.

## History

- 2026-09-10: Checked against the tree and not fired. The shell binds `CORTEX_BODY_ADDR`, defaulting
  to `127.0.0.1:50151` and documented in `docker/docker-compose.body.yml` as the setting an operator
  widens to `0.0.0.0:50151`, and the only authentication in front of that socket is
  `RpcTokenValidator`, one shared `x-cortex-seam-token` compared in constant time and passing
  everything through when the configured token is empty.
- 2026-09-12: Checked again and unchanged, and the entry now names the places rather than the
  posture. The reading worth recording is the dependency: this tree compiles no TLS at all, so
  enabling `tls-ring` or `tls-aws-lc` is the first step of any mTLS work rather than a detail of it.
- 2026-09-17: Checked again and unchanged, with two corrections. The body said credentials reach
  four places and named two; all four are named now. The trigger named a fact about the machine that
  the tree cannot record, so it now names where the tree records that fact. Neither has moved: the
  assumption still reads single-user, the base compose file publishes the brain's port on
  `127.0.0.1` only, and the lockfile still resolves tonic to 0.14.6.
