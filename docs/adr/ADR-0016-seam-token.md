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

## Addendum (2026-08-03): the header's three declarations are tied by a gate

The Consequences note above ("renaming the header touches server, client, and compose") stayed
true and stayed unenforced: `SEAM_TOKEN_HEADER` is declared by hand three times, in
`body/crates/rpc/src/auth.rs`, `body/crates/rpc/src/client.rs`, and `brain/packages/seam`, and
no test anywhere compared them. `scripts/crosscheck.py` now does, as one entry in its registry
of cross-language constants; the mechanism and why the seam token is in it are argued in
[ADR-0029](ADR-0029-vision-screen-capture.md)'s cross-language-constant addendum, and the scan
is documented in [docs/modules/repo-gates](../modules/repo-gates.md). Nothing about the token
itself changes here.

The compose healthcheck in `docker/docker-compose.yml` holds a **fourth** copy, inline in a
one-line Python command rather than as a declaration, so the gate does not reach it: a rename
would still break the healthcheck silently. That is recorded as an open deferral in
[docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates) rather than solved by teaching a
constant scanner to read a shell string embedded in YAML.

## Addendum (2026-08-25): the live suite's token precondition is checked, not merely implied

The Risks section above named the papercut this decision would cause and pointed at the runbooks to
mitigate it: "a configured brain + an unconfigured body fails loudly". The direction that actually
bit is the mirror of it, an **unconfigured brain** plus a check that needs a configured one, and no
runbook covered it because the instructions that mattered were not in a runbook. `just seam-health`
carried its own, in the comment above the recipe, and they said "Needs a running brain (`just up`
or `just brain-serve`)" and stopped there. Following them exactly produces a red suite:
`a_rejected_seam_token_is_answered_at_once_and_never_retried` dials with a deliberately wrong token
and a brain serving without one accepts it, so the check reports the brain as `Ready` and fails.

That check is right and stays as it is. A token-free brain's interceptor is a pass-through, so
there is no rejection to observe, and the check says so in its own failure message rather than
skipping, on the standing principle that a live check which quietly opts out is worse than one that
says what it needs. What was wrong is that the instructions produced the failure and then could not
explain it: at a glance a red check meaning "you configured it wrong" reads exactly like one
meaning "the seam regressed", and the reader has no way to tell which without opening the source.

**Decision: the recipe refuses to start without the token, before it spends a build.** `just
seam-health` now checks `CORTEX_SEAM_TOKEN` first and, when it is empty, prints what the suite
needs and both ways forward: serve with a token and present the same value here, or run the rest of
the suite by hand with that one check skipped and say so in what is reported. The recipe comment
states the precondition too, so the instruction and the enforcement agree.

Three things this deliberately is not.

**Not a new demand.** Five of the eight checks present the token to the brain already, so a suite
run against a protected brain needs the variable in its own environment whatever this recipe does.
Requiring it states the precondition rather than adding one.

**Not read off the running brain.** The recipe could ask docker what token the container serves
with, and then it would know only about a dockerized brain: `just brain-serve` has no container to
ask. It would also widen where the secret travels, to buy the operator nothing they do not already
have, since the value is one they chose.

**Not a skip.** Skipping the check when the token is absent would make the common misconfiguration
invisible, which is the failure mode the check was written against. The suite would go green while
proving nothing about the token at all.

### Distrust green

The guard is proven to fire, and the check behind it is proven still able to catch what it is for:

| Condition | Result |
| --- | --- |
| `CORTEX_SEAM_TOKEN` unset | `just seam-health` exits 1 before building, naming the two ways forward |
| Token set, brain serving without one | 7 passed, 1 failed, in 6.42 s: "the brain accepted a deliberately wrong token, so it is serving without auth" |
| Token set, brain serving with the same value | 8 passed, 0 failed, in 6.41 s |

The middle row is the evidence that the guard is a signpost rather than a substitute: an operator
who exports a token the brain does not serve with gets past it and then gets the check's own
message, which names the fix. It was measured by taking the stack down and back up without a token,
not inferred from the run this pass began with, where nothing was exported at all and the recipe
said nothing about it.

### What this opens

One papercut is left standing, and named where an operator meets it rather than solved: a token
written into the git-ignored `.env` reaches compose, which reads that file, and never reaches
`just`, which does not, so `just up` serves with a token that `just seam-health` cannot see. The
guard's message says so. The fix, teaching the justfile to load the same file, has consequences for
every recipe rather than this one, so it is
[R-441](../refinements/tasks/441-a-token-in-dotenv-reaches-compose-and-not-just.md).
