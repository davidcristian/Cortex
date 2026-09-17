# A disconnect mid handoff blocks stream teardown

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** a client event that does not need the cortex, observed waiting behind a `Cancel`'s
restore on a stack running handoffs. That observation is off-tree: no stack
here runs a handoff, and `grep -rnE 'CORTEX_ESCALATION: *[^ ]' docker/` finding nothing says no
shipped file turns the switch on. The gpu overlay passes it through by name, so a host `.env` can.
**Verified:** 2026-09-17

A disconnect mid handoff blocks the stream's teardown until the cortex is back.
Opened 2026-07-17 by the brain-handoff conductor sub-slice
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 5). The swap back is the recovery path,
so `swap_scope`'s restore now runs as its own shielded task and **every** cancellation waits for
it before propagating: without that, a client that disconnected while the cortex was coming back
left the process with no resident model and every later turn failing (found by the chaos suite,
and fixed there). Every one and not just the first, because this stream delivers two whenever a
client `Cancel` is followed by the stream's own teardown (`_cancel_turn` from the pump, then
again from `events()`'s `finally`), and a single shielded wait is abandoned by the second, which
put the drain window back up while the GPU was still empty. The cost is on the other side: the
Converse stream's `_cancel_turn` awaits the
turn task, so a `Cancel` or a disconnect during a handoff holds the RPC's teardown for as long as the
restore takes, which is seconds against the scripted host and minutes against real weights. The
alternative is to detach the restore (fire it, return, and let boot recovery be the backstop),
which trades a bounded wait for a window where the process records nothing as resident while a
restore it no longer tracks is still running. The trigger is a client event that waits behind
that restore without needing the cortex it restores (the 2026-09-17 trail line says why that is
the only case the wait costs anything); the fix belongs with the in-flight-turn lifecycle above,
not on its own.

## Trail

- 2026-07-17: opened by the brain-handoff conductor sub-slice, taking seam transport from 3 entries
  to 4. It is one of three entries three areas gained that day, the backlog working as intended
  rather than scope leaking: the capability landed and the three things it consciously did not do
  were written down. The restore is now uninterruptible, a cancellation waiting for it, because the
  chaos suite found that abandoning it midway left the process with no resident model at all, and
  the bounded wait that buys is the deliberate trade, to be revisited with the in-flight-turn
  lifecycle.
- 2026-07-19: given a line in the index's pickup order, which it had lacked since being written up.
  It was one of four entries the brain-handoff sub-slices opened that were recorded in their area
  docs and in the index's narrative with nothing saying when to pick them up, and the line named the
  trigger as a deployment where that wait holds a teardown long enough to matter.
- 2026-08-09: a trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing.
- 2026-09-10: read against the tree and still not fired. Both halves of the mechanism are where
  this entry left them: `ResidencyController.swap_scope` still ends in a `finally` that awaits
  `restore_uninterruptibly(self._restore(model))`, and `ConverseStream._cancel_turn` still ends in
  `await asyncio.wait([turn])`, so a cancellation during a swap still holds the RPC's teardown for
  the length of the restore. The trigger asks for a deployment, and this repo has none: the handoff
  is off unless `CORTEX_ESCALATION` is set, no compose file sets it, and the only place it is
  written is a comment in `docker/docker-compose.gpu.yml` telling an operator what to add.
- 2026-09-17: re-derived and still not fired, and the trigger was restated as a condition a run
  can answer. The mechanism is unchanged: `ResidencyController.swap_scope` still awaits
  `restore_uninterruptibly(self._restore(model))` in its `finally` (`residency.py:143`), and
  `ConverseStream._cancel_turn` still ends in `await asyncio.wait([turn])`
  (`converse_stream.py:224`). What the old trigger never said is who waits on that teardown. After
  a disconnect nobody does in this process except shutdown, whose grace is 5 s
  (`server.py:53`). After a `Cancel` it is the stream's own pump, which awaits `_cancel_turn`
  (`converse_stream.py:174`) and so reads no further client event until the restore ends. A
  cancelled turn emits no terminal event, so the body is not waiting for one. The next `UserTurn`
  is the event that waits, and it needs the cortex the restore is bringing back, so detaching the
  restore would free the pump without letting that turn start any sooner. That makes the hold
  matter only for an event that does not need the cortex, which is what the trigger now names.
  One bound was read beside it, not run: the restore's readiness gating alone can reach
  `_RESTORE_ATTEMPTS` 2 times `DEFAULT_SWAP_LOAD_TIMEOUT_S` 300 s, which equals the body's
  `DEFAULT_TURN_FIRST_GAP_MS` of 600 s, so a turn sent into a worst-case restore can be ended by
  the body before it starts. That holds equally for a turn that arrives mid-handoff with no
  `Cancel` and waits for the same restore, so it belongs to the silent-turn heartbeat entry
  ([R-421](421-a-silent-turn-owes-the-body-a-heartbeat.md)) and not to this one. No commit since
  2026-09-10 touched either site.
