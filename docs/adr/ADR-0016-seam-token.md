# ADR-0016: The seam shared-secret token (assumption 5 made real)

- **Status:** Accepted (Phase-0 assumption 5 hardening, landed 2026-07-03)
- **Date:** 2026-07-03

## Context

ROADMAP assumption 5 states the seam's security model: *"loopback-only listeners,
shared-secret token on the seam via env, no mTLS."* Only the first half was implemented (
compose publishes every port on `127.0.0.1`), while the token half existed nowhere: the brain
served with `add_insecure_port` and zero auth, the body dialed with none, and the gap was not
even recorded as a deferral. Concretely, **any process on the host** (a browser exploit, a
rogue npm postinstall, any other user-level code) could drive the brain: read session history
via `Converse`, burn GPU cycles, plant memory entries, and call every tool the cortex holds,
today read-only filesystem/email, later gated OS actions. Loopback-only stops remote hosts;
it does nothing about local processes.

## Decision

1. **A shared secret in `CORTEX_SEAM_TOKEN`, read from env on both sides** (never the repo;
   compose passes it through from the host env / git-ignored `.env`). Empty (the default)
   disables the check, so the dev loop, CI, and existing deployments run unchanged, and
   loopback-only remains the outer boundary.
2. **The brain enforces it structurally, in a server interceptor** (`cortex_orchestrator.auth`,
   `SeamTokenInterceptor`, registered by `create_server` iff the token is set). Every RPC (
   present and future, so no per-method discipline) must carry the token as
   `x-cortex-seam-token` metadata or is aborted `UNAUTHENTICATED` before any servicer code
   runs, through a rejection handler matching the method's own streaming shape. The compare is
   constant-time (`secrets.compare_digest`); the denial does not reveal whether the token was
   absent or wrong.
3. **The body attaches it in a tonic client interceptor** (`BrainSeamClient::connect_with_token`;
   plain `connect` sends none). The interceptor holds the parsed metadata value and is
   deliberately not `Debug`. Combined with tonic printing interceptors by type name, the
   secret cannot reach a log via `{:?}`. The Tauri shell reads the same `CORTEX_SEAM_TOKEN`
   env var and passes it on connect.
4. **The compose healthcheck carries the token too** when configured. Otherwise enabling
   auth would flap the brain container unhealthy.
5. **No mTLS, no per-RPC authorization, by design.** Single user, loopback plaintext; the
   token authenticates "a process the user configured", nothing finer. Revisit (assumption 5
   unchanged) only if anything ever listens beyond loopback.

## Consequences

- The seam's documented posture and its implementation now agree; enabling it is one env var
  on both sides (`CORTEX_SEAM_TOKEN=<value>` for the compose stack and the body process).
- The threat stopped is the realistic local one: arbitrary user-level code driving the
  assistant's tools and memory. What it does not stop: a same-user attacker who can read the
  body's process environment (they already own the account); and loopback traffic sniffing
  needs elevated privileges. Both accepted for a single-user machine.
- `create_server` gains one branch; with the token unset the server is byte-for-byte the
  previous one (no interceptor registered at all).
- The Rust client's channel type is now uniformly interceptor-fronted (a pass-through when
  token-less), so `connect` and `connect_with_token` share one code path and one client type.

## Risks

- **A configured brain + an unconfigured body fails loudly** (`UNAUTHENTICATED` surfaces as a
  `TransportError::Rpc` in the overlay), which is intentional and diagnosable, but a setup papercut;
  the runbooks name the env var on both sides.
- **The token rides plaintext HTTP/2 on loopback.** Acceptable per the posture above; mTLS is
  the recorded escalation if the seam ever leaves loopback.
- **Healthcheck coupling:** the check embeds the metadata key; renaming the header touches
  server, client, and compose (all under `SEAM_TOKEN_HEADER` constants / one compose line).

## Deferred

- **Token rotation / multiple tokens** is pointless for one user-managed pair; revisit with
  any second client.
- **mTLS on the seam** matters only if anything ever listens beyond loopback (assumption 5's
  standing trigger).
