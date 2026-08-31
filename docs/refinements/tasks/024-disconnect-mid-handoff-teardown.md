# A disconnect mid handoff blocks stream teardown

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** a real deployment where a disconnect during a swap holds a teardown long enough to matter.

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
restore it no longer tracks is still running. The trigger is a real deployment where a
disconnect during a swap holds a teardown long enough to matter; the fix belongs with the
in-flight-turn lifecycle above, not on its own.

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
