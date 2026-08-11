# Safe `converse` reconnect before the first event

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** routine mid-turn evictions once the real model swap lands, and turns costly enough that a silent re-run beats paying for dedup.

Its one-line cost ("a
replayable request and a signature change") was right about the shape and silent about the size.
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
partial reply dropped" design. Disproportionate at personal loopback scale where reconnects are
rare and a dropped turn is already terminal (the user resends), so it waits for a trigger: routine
mid-turn evictions once the real model swap lands, and turns costly enough that a silent re-run
beats paying for dedup. `converse` stays unretried (`SeamMethod::Converse` is not repeatable);
this sharpen is why, not a change to it.

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
