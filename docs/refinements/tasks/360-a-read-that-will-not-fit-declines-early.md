# A read RPC with milliseconds left still spends the round trip

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** A store read whose duration is measured rather than guessed, meaning a distribution
this repo keeps rather than one number somebody picked; or the body's own bound ceasing to be
shorter than the deadline it announces, which is what currently makes the handler's own return
worth so little.

`ListSessions` reads `time_remaining()` nowhere. It calls `SessionStore.list_sessions` whatever the
clock says, and a caller who has already given up gets a reply written into a stream nobody reads,
which the abandonment interceptor logs and nothing else notices. The shape asked for is a handler
that sees milliseconds left and answers `DEADLINE_EXCEEDED` at once rather than spending a Redis
round trip on it.

It was weighed and declined on 2026-08-21, for two reasons that are worth keeping separate.

The first is the one the shape has carried since it was written: what "will not fit" means. A fixed
floor is a number nobody has measured, and this repo has no histogram of how long a store read
takes. The knob would ship with a guess, and a guess on this particular branch is dangerous in a
way a guess elsewhere is not, because being wrong low costs nothing visible and being wrong high
refuses reads that would have succeeded. There is no reading anywhere in the tree that would tell
an operator which of the two they had.

The second is the one that only became clear on re-derivation, and it is the heavier. The body
announces a deadline strictly longer than the bound it enforces (the grace margin), so by the time
the handler could see "milliseconds left" the caller has usually stopped waiting already, and
grpc.aio has cancelled the coroutine on its own clock. The handler's early return is therefore
mostly a saving of one Redis round trip on a call that is already over. That is real but small, and
it is bought with a branch that answers `DEADLINE_EXCEEDED` for a deadline that has **not** expired:
the brain would be inventing an expiry, on its own reading, some milliseconds before the real one.
For a store this side of a loopback socket, that trade does not pay.

What would change it is a read that is genuinely expensive, which is what the trigger names. A
paging cursor ([184](184-paging-cursor.md)) or a catalog large enough that a listing is not a
round trip but a scan would make the saving worth the invented expiry, and would also be the thing
that finally produces a measurement to set the floor from.

## Trail

- 2026-08-21: Filed by the close of
  [341](341-nothing-declines-work-it-cannot-finish.md), which decided all three of its shapes and
  built the one that was not a per-RPC policy. Recorded in the ADR-0024 addendum on what the
  announced deadline is worth downstream.
