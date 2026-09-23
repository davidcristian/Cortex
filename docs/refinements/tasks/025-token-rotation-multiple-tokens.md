# Token rotation and multiple tokens

**Status:** open, waiting for a consumer
**Area:** rpc-auth
**Origin:** [ADR-0016](../../adr/ADR-0016-shared-token.md)
**Trigger:** A second party on this connection, meaning a client the pair's own operator does not run, whose credential has to be withdrawn without disturbing the other.
**Verified:** 2026-09-19

Rotating or issuing several tokens buys nothing for one body and brain pair run by one person.
The other deferred item from the same ADR, mTLS on a non-loopback link, is recorded at
[R-219](219-hardened-non-loopback-posture.md), which also costs the cheaper half of this one,
splitting the shared secret into a per-direction pair.

The trigger as first worded asked for a second client, and a second client exists: the brain is a
client of the body's `BodyService`, and `docker/docker-compose.body.yml` gives that direction the
same shared `CORTEX_SEAM_TOKEN` the Tauri body presents to `BrainService`. The one secret reaches
four readers: `converse.rs` and `brain.rs` in the body's shell attach it outbound, `body_server.rs`
compares it inbound, and the brain reads it once as `RpcServerConfig.token`, which `wiring.py`
hands both to its own interceptor and to the outbound body gateway. Nothing follows from that for
rotation, because both clients are halves of the one pair this entry called pointless to rotate
for: rotating them means restarting both processes with a new value, which one operator does in
one step. Rotation buys something only when a credential has to be withdrawn from one holder while
another keeps working, which is what the trigger now asks for.

## History

- 2026-07-15: Moved out of the ROADMAP's deferred-refinements section into this backlog, listed as
  needing a second client.
- 2026-09-13: Checked again. A second client had arrived with the brain to body direction, both
  clients presenting one `CORTEX_SEAM_TOKEN`, so the trigger was narrowed from a second client to
  a second party.
- 2026-09-19: Checked again, and the trigger has not fired. Outside tests and probes, the one
  `CORTEX_SEAM_TOKEN` is still read in four places: `converse.rs`, `brain.rs` and `body_server.rs`
  in the shell, and `RpcServerConfig.token` in the brain. The rest of what presents it is the
  deployment checking itself: the brain container's compose healthcheck, `just rpc-health`, which
  runs `body/crates/rpc/tests/live.rs`, and the brain's `integration`-marked live tests. Those run
  under the same operator on the same machine. No compose file, runbook or default gives the token
  to anything the pair's operator does not run.
