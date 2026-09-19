# Safe `converse` reconnect before the first event

**Status:** open, waiting for its trigger
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** a deployment that sets `CORTEX_ESCALATION`, which is the switch that builds a swap
scope at all (`brain/packages/orchestrator/src/cortex_orchestrator/swap_builders.py:103` returns
`None` without it), together with turns costly enough that a silent re-run beats paying for dedup.
Recheck with `grep -rnE 'CORTEX_ESCALATION: *[^ ]' docker/`: no hit means no shipped file turns
the switch on and this has not fired. The gpu overlay passes it through by name, so a host `.env`
can.
**Verified:** 2026-09-17

Retrying a `converse` turn after a disconnect is only safe if the brain can tell that the repeat
is the same request. It cannot. A turn's first durable effect is
`await self._store.append(session_id, user)` in `TurnEngine.handle_turn` (`engine.py`), which runs
before inference and before the first yielded event, on a turn task that advances whether or not
the client reads (`converse_stream.py`: a `UserTurn` starts `_turn_task` and its events go onto a
queue the consumer drains separately). So "the client saw no event" never means "the brain did
nothing": by then the user message is stored and a tool the model asked for first may have run.
Nothing on the wire identifies the request either: `ClientEvent` and `UserTurn` contain
`session_id`, text and images, with no request id or idempotency key, and the `turn_id` is created
on the server, so a reconnect that re-issues the request runs the turn twice. Verified live
against the real engine: an identical resend leaves two user messages under two distinct turn ids.

A safe version needs a client-generated request id (a proto field and both stubs regenerated) or a
resumable cursor, plus a Redis-backed idempotency and resume registry keyed by
`(session_id, request_id)` that survives a model swap, which either replays a completed turn's
outcome or re-attaches to an in-flight turn's buffered events. That is a turn-lifecycle state
machine, an idempotency store and an event-replay path, and it reverses the deliberate design that
an in-flight turn is disposable and its partial reply dropped. That is too much at personal
loopback scale, where reconnects are rare and a dropped turn is already terminal because the user
resends. `converse` stays unretried, `SeamMethod::Converse` not being repeatable.

## History

- 2026-07-08: Recorded as deferred inside the transport retry policy entry, costed there at a
  replayable request and a signature change.
- 2026-07-16: Audited against both sides of the interface and sharpened rather than built. The
  user-message `store.append` in `handle_turn` runs before inference and before the first event,
  on a turn task decoupled from client reading, and nothing on the wire identifies the request, so
  a reconnect that re-issues it runs the turn twice, verified live as two user messages under two
  distinct turn ids.
- 2026-08-09: A review read this at the site that would have had to move and found nothing:
  nothing is routinely evicted while `CORTEX_SWAP_EVICT_MODELS` is empty by default.
- 2026-09-08: Read again at the switch above that setting and still nothing. `CORTEX_ESCALATION`
  decides whether a swap scope is built at all, and it appears once in `docker/`, in a comment;
  the shipped defaults are `escalation=False` and `modelhost_backend="none"`. The trigger was
  rewritten to name that switch and the command that reports it.
- 2026-09-11: The prescribed grep still reports one hit, the comment at
  `docker/docker-compose.gpu.yml:25`, and `build_swap_scope` still returns `None` without the
  switch, now at `swap_builders.py:103-104`. `ClientEvent` and `UserTurn` still identify no
  request (`proto/body.proto:93-105`), the user message is still appended before inference at
  `engine.py:118`, and the turn still runs on its own task from `converse_stream.py:208`.
- 2026-09-17: The prescribed grep still reports its one hit, and no compose file has an `env_file`
  key, so a `.env` alone cannot turn the switch on inside the brain container. Every citation
  above holds at the same lines and no commit since 2026-09-11 touched those files. The one
  change in this area since, the raised idle gap in `body/crates/core/src/retry/gap.rs`, bounds a
  turn's silence and leaves `repeatable` answering false for `Converse`. One sentence of the
  2026-09-11 line was wrong: `Converse` is not the only method `repeatable` answers false for. It
  is one of six (`plan.rs:157-162`), the others being `AckReminder`, `RenameSession`,
  `DeleteSession`, `SetSessionPinned` and `SetPreference`. It is the only method `deadline_for`
  answers `None` for, which is the half [R-360](360-a-read-that-will-not-fit-declines-early.md)
  depends on, so that line's conclusion stands.
