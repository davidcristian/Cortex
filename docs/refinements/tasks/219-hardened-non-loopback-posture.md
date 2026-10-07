# A hardened non-loopback posture

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** ROADMAP assumption 5, the security model in `docs/ROADMAP.md` that says the machine
is single-user with loopback-only listeners except the body's and a shared-secret token, being
revised to admit a second user or a body and brain on different machines; or any compose file,
runbook or default in the tree putting a listener where a second machine reaches it past the host
firewall the body override relies on. Whether the machine really has one user is not something
the tree can record; that assumption is where the tree says so. The compose half is decided by
listing every `ports:` entry under `docker/`: each starts with `127.0.0.1:` while not fired.
**Verified:** 2026-10-07

The body binds a configurable interface, loopback for development and `0.0.0.0` for the
container-to-host path, behind the shared token and the host firewall. mTLS or per-direction tokens
would be wanted if the machine ever stops being single-user.

Transport credentials reach four places, one per end of each direction, plus one dependency. On the
brain-to-body direction, the brain opens the channel with `aio.insecure_channel` in
`GrpcBodyGateway.connect` (`brain/packages/body_client/src/cortex_body_client/gateway.py`), which
would take channel credentials and a trust root from configuration, and the body serves
`Server::builder()` over a plain `TcpListenerStream` in the Tauri shell's `body_server::serve`,
which the Windows and the Linux `start` both call and which would take a server TLS config and,
for mutual authentication, a client certificate root. On
the body-to-brain direction, the brain serves with `server.add_insecure_port` in
`brain/packages/orchestrator/src/cortex_orchestrator/server.py`, and the body dials with
`Channel::from_shared` in `body/crates/rpc/src/client.rs`, which the shell reaches through
`BrainRpcClient::connect_lazy_with_token`.

The dependency is the one thing here that is not a line of code: `body/Cargo.toml` and the Tauri
shell's own `body/app/src-tauri/Cargo.toml` each declare `tonic = "0.14"` with default features,
both lockfiles resolve it to 0.14.6, and its defaults are `router`, `transport` and `codegen`, so no
TLS is compiled into this tree at all and one of the `tls-ring` or `tls-aws-lc` features has to be
enabled first.

Splitting the one shared secret into a per-direction pair is separate and cheaper. Each side reads
`CORTEX_SEAM_TOKEN` for both directions: the brain reads it once, as `token` on the `CORTEX_SEAM_`
settings in `cortex_orchestrator/config.py`, and hands it to `RpcTokenInterceptor` in `server.py`
and to `build_body_gateway` in `wiring.py`; the shell reads it three times, for its two brain
clients in `brain.rs` and `converse.rs` and for `RpcTokenValidator` in `body_server.rs`. A second
variable means a second setting in the brain, a new read in `body_server.rs`, and the docs that
describe one token for both directions: the row in the `docs/runbooks/local-dev-wsl.md` settings
table, the sentence in `docs/runbooks/body-volume.md`, and the `body-app` and
`brain-orchestrator-config` module docs.

The certificate lifecycle, not the code, is what makes this wait: a single-user machine has nowhere
to put a private certificate authority that the host firewall does not already cover.

## History

- 2026-09-10: Checked against the tree and not fired. The shell binds `CORTEX_BODY_ADDR`, defaulting
  to `127.0.0.1:23151` and documented in `docker/docker-compose.body.yml` as the setting an operator
  widens to `0.0.0.0:23151`, and the only authentication in front of that socket is
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
- 2026-09-24: Checked again and not fired. Every compose file still publishes on `127.0.0.1` only,
  and the four places and both token readers are as named. Two corrections: the shell declares
  tonic in a manifest of its own, and assumption 5 said loopback-only listeners while the body
  override has the body bind `0.0.0.0:23151`, so the ROADMAP now names that exception.
- 2026-10-03: Checked again and not fired. Assumption 5 still reads single-user, and all 13
  `ports:` entries under `docker/` publish on `127.0.0.1`. Both lockfiles still resolve tonic to
  0.14.6 with no TLS crate in either. Two corrections: since the shell started serving on Linux, the
  server is built in `body_server::serve`, which both platforms' `start` call; and the token
  paragraph had each checker reading the variable for both directions and cited a compose sentence
  that is not there, so it now names the brain's one read, the shell's three, and the runbook.
