# Token rotation / multiple tokens

**Status:** open, dead until a consumer
**Area:** seam-auth
**Origin:** [ADR-0016](../../adr/ADR-0016-seam-token.md)
**Trigger:** A second party on this seam, meaning a client the pair's own operator does not run, whose credential has to be withdrawn without disturbing the other.
**Verified:** 2026-09-19

Pointless for one user-managed body↔brain pair;
revisit with any second client (ADR-0016 deferred). The other ADR-0016 deferral, mTLS on a
non-loopback seam, is recorded at the hardened non-loopback posture entry
([R-219](219-hardened-non-loopback-posture.md)), which also prices the cheaper half of this one,
splitting the shared secret into a per-direction pair.

**Corrected 2026-09-13: a second client exists, so the trigger as first worded has fired and it
asked the wrong question.** The brain is a client of the body's `BodyService` (ADR-0023), and
`docker/docker-compose.body.yml` records that this direction presents the same shared
`CORTEX_SEAM_TOKEN` the Tauri body presents to `BrainService`. The one secret reaches four readers:
`converse.rs` and `seam.rs` in the body's shell attach it outbound, `body_server.rs` compares it
inbound, and the brain reads it once as `SeamServerConfig.token`, which `wiring.py` hands both to
its own interceptor and to the outbound body gateway. Two clients and two servers therefore
authenticate from one value, and nothing follows from that for rotation, because both clients are
halves of the one pair this entry called pointless to rotate for: rotating them means restarting
both processes with a new value, which is what one operator does in one step. What would make
rotation buy something is a credential that has to be withdrawn from one holder while another keeps
working, and the trigger above now names that instead.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc with the
  entry kept verbatim, and carried in the index's dead-until-a-consumer bucket as "Token rotation /
  multiple tokens: needs a second seam client".
- 2026-09-13: Re-derived. A second client of the seam landed with the brain→body direction after this
  entry was written, both clients presenting one `CORTEX_SEAM_TOKEN`, so the trigger is narrowed
  from a second client to a second party. The pointer to the sibling deferral was repointed at the
  task file that now holds it, which already names what a per-direction split would cost.
- 2026-09-19: re-derived, and the trigger has not fired. Outside tests and probes, the one
  `CORTEX_SEAM_TOKEN` is still read from the environment in four places: `converse.rs`, `seam.rs`
  and `body_server.rs` in the shell, and `SeamServerConfig.token` in the brain, which `wiring.py`
  passes to the outbound body gateway as well as to the interceptor. The rest of what presents it is
  the deployment checking itself: the brain container's compose healthcheck, which calls `Health` with
  it (`docker/docker-compose.yml`), `just seam-health`, which runs `body/crates/rpc/tests/live.rs`,
  and the brain's `integration`-marked live seam tests. Those run under the same operator on the same
  machine, so they are more clients of one party rather than a second party. No compose file,
  runbook or default gives the token to anything the pair's operator does not run.
