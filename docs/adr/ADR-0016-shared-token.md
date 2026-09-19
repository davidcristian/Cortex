# ADR-0016: The shared-secret token between body and brain

**Status:** Accepted (2026-09-13)

## Context

The roadmap states the security model for the body to brain connection: *"loopback-only listeners,
shared-secret token via env, no mTLS."* Only the first half was implemented (compose publishes
every port on `127.0.0.1`), while the token half existed nowhere: the brain served with
`add_insecure_port` and no authentication, the body connected with none, and the gap was not even
recorded as a deferral. Concretely, **any process on the host** (a browser exploit, a rogue npm
postinstall, any other user-level code) could drive the brain: read session history through
`Converse`, burn GPU cycles, plant memory entries, and call every tool the cortex holds, read-only
filesystem and email at first, OS actions later. Loopback-only stops remote hosts; it does nothing
about local processes.

## Decision

1. **A shared secret in `CORTEX_SEAM_TOKEN`, read from the environment on both sides** (never the
   repo; compose passes it through from the host environment or the git-ignored `.env`). Empty (the
   default) disables the check, so the dev loop, CI, and existing deployments run unchanged, and
   loopback-only remains the outer boundary.
2. **The brain enforces it in a server interceptor** (`cortex_orchestrator.auth`,
   `SeamTokenInterceptor`, registered by `create_server` only when the token is set). Every RPC,
   present and future, so no per-method discipline is needed, must present the token as
   `x-cortex-seam-token` metadata or is aborted `UNAUTHENTICATED` before any servicer code runs,
   through a rejection handler matching the method's own streaming form. The comparison is
   constant-time (`secrets.compare_digest`), and the denial is identical for an absent token and a
   wrong one.
3. **The body attaches it in a tonic client interceptor** (`SeamTokenInterceptor` in
   `body/crates/rpc/src/call.rs`, reached through `BrainSeamClient::connect_with_token`; plain
   `connect` sends none). The interceptor holds the parsed metadata value and deliberately does not
   derive `Debug`. Since tonic prints interceptors by type name, the secret cannot reach a log
   through `{:?}`. It is built per call rather than per client because it also holds the call's
   announced deadline ([ADR-0024](ADR-0024-transport-retry.md) decision 15). The Tauri shell reads
   the same `CORTEX_SEAM_TOKEN` environment variable and passes it on connect.
4. **The compose healthcheck presents the token too** when configured. Otherwise enabling
   authentication would flap the brain container unhealthy.
5. **No mTLS, no per-RPC authorization, by design.** Single user, loopback plaintext; the token
   authenticates "a process the user configured", nothing finer. Revisit (with the roadmap's
   assumption unchanged) only if anything ever listens beyond loopback.
6. **The header name is checked to be the same everywhere it is written.** `SEAM_TOKEN_HEADER` is
   declared by hand three times, in `body/crates/rpc/src/auth.rs`, `body/crates/rpc/src/call.rs`
   and `brain/packages/seam` (`cortex_seam`), and the compose healthcheck writes it a fourth time
   inside a one-line Python command. `scripts/crosscheck.py` compares all four as one entry of its
   registry ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)), so a rename that misses one
   fails `just check` rather than every authenticated call.
7. **One token covers both directions.** The brain-to-body direction
   ([ADR-0023](ADR-0023-body-gateway-volume.md)) authenticates with the same `CORTEX_SEAM_TOKEN`,
   as `docker/docker-compose.body.yml` states. The brain reads it once, as
   `SeamServerConfig.token`, and its wiring hands that value both to its own interceptor and to the
   outbound body gateway. In the body's shell, `converse.rs` and `seam.rs` attach it outbound and
   `body_server.rs` checks it inbound through `SeamTokenValidator`
   (`body/crates/rpc/src/auth.rs`). The validator is always attached and passes every call when the
   token is empty, the single-type equivalent of the brain registering its interceptor only when
   set; its comparison is constant-time and it does not derive `Debug`. Two clients and two servers
   therefore authenticate from one secret.
8. **The live suite checks its token precondition before it builds.** One live check proves a wrong
   token is refused at once, and a brain serving without a token accepts every token, including the
   deliberately wrong one, so against a token-free brain that check fails. It fails with that as
   its message rather than skipping, because a live check that opts out silently reports success
   without having tested anything. `just seam-health` exits when `CORTEX_SEAM_TOKEN` is unset,
   before it runs a build, and prints both ways forward: serve with a token and present the same
   value, or run the rest of the suite by hand with that one check skipped and say so in what is
   reported. The recipe comment states the same precondition. A failure meaning "configured wrong"
   otherwise looks exactly like one meaning "the connection broke", and telling them apart would
   mean opening the source. The guard adds no new requirement, since most checks in the suite
   present the token already; it does not read the token off the running brain, which would cover
   only a dockerized brain (`just brain-serve` has no container to ask) and would widen where the
   secret travels.

## Consequences

- The documented security posture and its implementation agree; enabling it is one environment
  variable on both sides (`CORTEX_SEAM_TOKEN=<value>` for the compose stack and the body process).
- The threat stopped is the realistic local one: arbitrary user-level code driving the assistant's
  tools and memory. What it does not stop: a same-user attacker who can read the body's process
  environment (they already own the account); and sniffing loopback traffic needs elevated
  privileges. Both accepted for a single-user machine.
- With the token unset, `create_server` registers no token interceptor. The
  `AbandonedCallInterceptor` ([ADR-0061](ADR-0061-abandoned-call-line.md)) is installed either way
  and goes after the token check, so an unauthenticated call is refused rather than watched.
- The Rust client's channel type always has an interceptor in front (a pass-through when there is
  no token), so `connect` and `connect_with_token` share one code path and one client type.

## Risks

- **A configured brain with an unconfigured body fails visibly** (`UNAUTHENTICATED` appears as a
  `TransportError::Rpc` in the overlay), which is intentional and diagnosable, but a setup
  papercut; the runbooks name the environment variable on both sides.
- **The token travels over plaintext HTTP/2 on loopback.** Acceptable per the posture above; mTLS
  is the recorded next step if the connection ever leaves loopback.
- **A token written in `.env` reaches compose, which reads that file, and never reaches `just`,
  which does not**, so `just up` serves with a token that is absent from `just seam-health`'s
  environment. The guard's message says so. Making the justfile load the same file changes every
  recipe rather than this one
  ([R-441](../refinements/tasks/441-a-token-in-dotenv-reaches-compose-and-not-just.md)).

## Deferred

- **Token rotation and multiple tokens**
  ([R-025](../refinements/tasks/025-token-rotation-multiple-tokens.md)). The second client
  (decision 7) is the other half of the one pair the operator runs, and rotating means restarting
  both processes with a new value, which one operator does in one step. Rotation buys something
  only when a credential has to be withdrawn from one holder while another keeps working, so the
  trigger is a second party on the connection rather than a second client. Splitting the secret
  into a per-direction pair is a separate and cheaper change, priced with the hardened posture
  below.
- **mTLS** matters only if anything ever listens beyond loopback (the roadmap's condition;
  [R-219](../refinements/tasks/219-hardened-non-loopback-posture.md)).

## Alternatives rejected

- **Skipping the wrong-token check when no token is set**: the suite would pass while proving
  nothing about the token, which is the misconfiguration the check was written against.
- **Parsing the healthcheck's YAML-embedded command with a dedicated scanner**: the constant
  registry's plain search for the value already reaches it (decision 6).

## Related

- Code: `brain/packages/orchestrator/src/cortex_orchestrator/auth.py`, `server.py`,
  `body/crates/rpc/src/auth.rs`, `call.rs`, `client.rs`, `body/crates/rpc/tests/live.rs`, the
  `seam-health` recipe in `justfile`, `scripts/seamcouplings.py`.
- Module docs: [body-rpc](../modules/body-rpc.md),
  [brain-orchestrator](../modules/brain-orchestrator.md).
- Runbook: [local-dev-wsl](../runbooks/local-dev-wsl.md).
- ADRs: [ADR-0023](ADR-0023-body-gateway-volume.md) (the brain-to-body direction),
  [ADR-0042](ADR-0042-cross-tree-constant-registry.md) (the constant registry).
