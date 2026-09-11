# Safe `converse` reconnect before the first event

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** a deployment that sets `CORTEX_ESCALATION`, which is the switch that builds a swap
scope at all (`brain/packages/orchestrator/src/cortex_orchestrator/swap_builders.py:103` returns
`None` without it), together with turns costly enough that a silent re-run beats paying for dedup.
Recheck with `grep -rn CORTEX_ESCALATION docker/`: one hit, inside a comment, means nothing swaps
and this has not fired.
**Verified:** 2026-09-11

The transport retry entry costed this at one line, "a replayable request and a signature
change", which was right about the shape and said nothing about the size.
Read against both sides of the seam: a `converse` turn's first durable effect is
`await self._store.append(session_id, user)` in `TurnEngine.handle_turn` (`engine.py`), run
before inference and before the first yielded event, on an independent turn task that advances
whether or not the client reads (`converse_stream.py`, a `UserTurn` starts `_turn_task` and its
events land on a queue the consumer drains separately). So "the client saw no event" never means "the
brain did nothing": by then the user message is stored and a tool the model asked for first may
have run. And nothing carries request identity: `ClientEvent` and `UserTurn` hold `session_id`,
text, and images, no request id or idempotency key, and the `turn_id` is minted server-side, so a
reconnect that re-issues the request double-runs the turn (verified live over the real engine, an
identical resend leaves two user messages under two distinct turn ids). A provably-safe version
needs a client-generated request id (a proto field, both stubs regenerated) or a resumable cursor,
plus a Redis-backed idempotency/resume registry keyed by `(session_id, request_id)` that survives
a model swap (the one hard rule) and either replays a completed turn's outcome or re-attaches to
an in-flight turn's buffered events. That is a turn-lifecycle state machine, an idempotency store,
and an event-replay path, and it reverses the deliberate "an in-flight turn is disposable, its
partial reply dropped" design. That is disproportionate at personal loopback scale, where reconnects are
rare and a dropped turn is already terminal (the user resends), so it waits for a trigger: routine
mid-turn evictions once the real model swap lands, and turns costly enough that a silent re-run
beats paying for dedup. `converse` stays unretried (`SeamMethod::Converse` is not repeatable);
this sharpening explains why, and does not change it.

Read again on 2026-09-08, one level above the knob the previous reading checked. An empty
`CORTEX_SWAP_EVICT_MODELS` says no peer tier is evicted, but the switch that decides whether any
handoff machinery exists is `CORTEX_ESCALATION`: with it off, `build_swap_scope` returns `None`
(`swap_builders.py:103`), so no conductor, no model host, and no swap of any kind is constructed,
whatever the eviction list holds. `grep -rn CORTEX_ESCALATION docker/` reports exactly one hit
today, a comment at `docker/docker-compose.gpu.yml:25` describing what an operator would set to
turn escalation on. The shipped defaults agree: `escalation` is `False` and `modelhost_backend` is
`"none"` (`config_swap.py:108-109`). So no model swap runs on any composed stack in this repo, and
the mid-turn eviction the trigger waits for cannot occur yet.

## Trail

- 2026-07-08: recorded as deferred inside the transport retry and reconnect policy entry, costed
  there at a replayable request and a signature change.
- 2026-07-16: audited against both sides of the seam and sharpened rather than built. A turn's first
  durable effect, the user-message `store.append` in `handle_turn`, runs before inference and before
  the first event on a turn task decoupled from client reading, and nothing on the wire carries
  request identity, so a reconnect that re-issues the request double-runs the turn, verified live
  over the real engine as two user messages under two distinct turn ids. It moved to
  fix-when-it-bites with its trigger named, so the area count was unchanged, which is the same
  bookkeeping the session-history and reranker sharpens used.
- 2026-08-09: the trigger sweep of that bucket read this one at the site that would have to have
  moved and found it quiet, nothing being routinely evicted while `CORTEX_SWAP_EVICT_MODELS` is
  empty by default (`brain/packages/orchestrator/src/cortex_orchestrator/config_swap.py:113`, the
  knob the recovery path names at `brain/packages/core/src/cortex_core/swap_recovery.py:101`).
- 2026-09-08: reread at the switch above that knob and still quiet. `CORTEX_ESCALATION` decides
  whether a swap scope is built at all, and it appears once in `docker/`, in a comment; the
  shipped defaults are `escalation=False` and `modelhost_backend="none"`. The seam side is
  unchanged: `ClientEvent` and `UserTurn` still carry `session_id`, text and images and no request
  identity (`proto/body.proto:93-104`). Left open with the trigger rewritten to name that switch
  and the command that reports it, recorded in the ADR-0024 addendum on what the two seam-transport
  triggers read on this date.
- 2026-09-11: the prescribed grep still reports one hit, the comment at
  `docker/docker-compose.gpu.yml:25`, and the switch it names still returns `None` from
  `build_swap_scope`, now at `swap_builders.py:103-104` (the line the entry cited had moved by
  six, repaired above). The shipped defaults are unchanged at `config_swap.py:108-109`. On the
  seam side `ClientEvent` and `UserTurn` still carry no request identity
  (`proto/body.proto:93-105`), the user message is still appended before inference at
  `engine.py:118`, and the turn still runs on its own task from `converse_stream.py:208`. Where
  this touches the read-deadline entry
  ([360](360-a-read-that-will-not-fit-declines-early.md)): both sit in
  `body/crates/core/src/retry/plan.rs`. `Converse` is the one method `repeatable` answers false
  for by design (line 157) and the one `deadline_for` answers `None` for (line 252), so it
  announces no deadline and the grace margin that entry turns on never reaches a turn; a request
  id here would leave the read handlers' clock untouched. The two entries agree, and neither lies
  on the other's path.
