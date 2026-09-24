# A disconnect mid handoff blocks stream teardown

**Status:** open, waiting for its trigger
**Area:** rpc-transport
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** a client event that loses by waiting for the restore, sent on a `Converse` stream
after a `Cancel`, since that stream's pump reads nothing else until the restore ends. Neither half
holds today. No member of `ClientEvent`'s `event` oneof in `proto/body.proto` loses by the wait: a
`user_turn` needs the cortex the restore brings back, and a `cancel` or `confirm_response` can only
answer the turn being cancelled. And the body sends no `Cancel`: it opens a fresh stream per turn
(`BrainTransport::converse`, `body/crates/core/src/transport.rs`), and a stop in the overlay only
stops delivery while the turn runs to its end (`TauriBridge.converse`), which
`grep -rn 'Cancel' body/crates/core/src body/crates/rpc/src body/app/src-tauri/src --exclude-dir=_generated`
finding nothing confirms. R-127 would add the `Cancel` half and not the other.
**Verified:** 2026-09-24

Swapping the cortex back in is the recovery path, so `swap_scope`'s restore runs as its own
shielded task and every cancellation waits for it before propagating. Without that, a client who
disconnected while the cortex was coming back left the process with no resident model and every
later turn failing, which the chaos suite found. Every cancellation and not just the first,
because this stream delivers two whenever a client `Cancel` is followed by the stream's own
teardown (`_cancel_turn` from the pump, then again from `events()`'s `finally`), and a single
shielded wait is abandoned by the second, which reopened the window while the GPU was still empty.

The cost is on the other side. The Converse stream's `_cancel_turn` awaits the turn task, so a
`Cancel` or a disconnect during a handoff holds the RPC's teardown for as long as the restore
takes, which is seconds against the scripted host and minutes against real weights. The
alternative is to detach the restore, letting boot recovery cover it, which trades a bounded wait
for a window where the process records nothing as resident while a restore it no longer tracks is
still running. The fix belongs with the in-flight-turn lifecycle
([R-023](023-converse-reconnect-first-event.md)) rather than on its own.

## History

- 2026-07-17: Opened by the brain-handoff conductor work. The restore is uninterruptible and a
  cancellation waits for it, because the chaos suite found that abandoning it midway left the
  process with no resident model at all. The bounded wait is the deliberate trade.
- 2026-07-19: Given a line in the index's pickup order, which it had lacked.
- 2026-08-09: A review of deferred triggers ran against the tree and none had fired.
- 2026-09-10: Read against the tree and still not fired. `ResidencyController.swap_scope` still
  ends in a `finally` that awaits `restore_uninterruptibly(self._restore(model))`, and
  `ConverseStream._cancel_turn` still ends in `await asyncio.wait([turn])`. The trigger asks for a
  deployment, and this repo has none: the handoff is off unless `CORTEX_ESCALATION` is set and no
  compose file sets it.
- 2026-09-17: Checked again and still not fired, and the trigger was restated as something a run
  can answer. Both sites are unchanged (`residency.py:143`, `converse_stream.py:224`). What the
  old trigger never said is who waits on that teardown. After a disconnect nobody does in this
  process except shutdown, whose grace is 5 s (`server.py:53`). After a `Cancel` it is the
  stream's own pump, which awaits `_cancel_turn` (`converse_stream.py:174`) and so reads no
  further client event until the restore ends. A cancelled turn emits no terminal event, so the
  body is not waiting for one, and the next `UserTurn` needs the cortex the restore is bringing
  back, so detaching the restore would free the pump without letting that turn start sooner. The
  hold therefore matters only for an event that does not need the cortex. One bound was read
  beside it: the restore's readiness checks alone can reach `_RESTORE_ATTEMPTS` times
  `DEFAULT_SWAP_LOAD_TIMEOUT_S` of 300 s, which equals the body's `DEFAULT_TURN_FIRST_GAP_MS` of
  600 s, so a turn sent into a worst-case restore can be ended by the body before it starts. That
  holds equally for a turn arriving mid-handoff with no `Cancel`, so it belongs to
  [R-421](421-a-silent-turn-owes-the-body-a-heartbeat.md).
- 2026-09-24: Not fired, and the trigger restated, because as written it could be met only by an
  event that loses nothing by the wait, and only from a client this repo does not have: the body
  sends no `Cancel`, and a stop leaves the turn running to its end, so a stream closes early only
  when a gap bound or the connection ends it. Both sites are unchanged, now at
  `residency.py:76` and `converse_stream.py:181`, the pump's await at `:135`. The 600 s concern
  above was not taken up by R-421's close, which keeps the ten-minute first gap and counts each
  heartbeat as 30 s of it. A turn that starts while a handoff holds the card now announces that
  wait before its first model call, so the first gap ends there, and a handoff whose scope begins
  after that check is
  [R-723](723-a-turn-that-starts-just-before-another-handoff-waits-unannounced.md).
