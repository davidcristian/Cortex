# A turn stream that stalls has no bound at all

**Status:** landed 2026-08-24
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Every unary call on this seam is now bounded, and the `converse` dial with them, but the turn's
own stream is deliberately not: `RetryPlan::deadline_for` answers `None` for `Converse` because a
turn is long by design and a clock is the wrong thing to end one. That decision is right about a
*working* turn and says nothing about a stalled one. A brain that accepts the turn and then emits
nothing leaves the overlay showing a thinking indicator forever, which is the same shape of harm
the probe had before it got a deadline, minus the latch: the user can cancel, so it is
recoverable rather than terminal, which is why this is not urgent.

What it needs is not a total deadline, which would kill long legitimate turns, but an **idle gap**
bound: the longest silence allowed *between* events, reset by every delta, tool activity and
status update. That is a stream decorator in the core over the existing `Sleeper` port rather than
a change to the port's signature, and the interesting part is choosing the gap honestly, since a
deep model on a cold cache can be quiet for a while before its first token while a mid-reply gap
of the same length means something is wrong. A first-token gap and a mid-stream gap may well be
two numbers.

## Trail

- 2026-08-18: opened by the per-attempt deadline ([301](301-seam-attempt-deadline.md)), which
  bounded every unary attempt and the eager dial and left the turn stream explicitly outside the
  bound, since ending a turn on a clock is a different decision with a different consumer.
- 2026-08-24: landed as `retry::gap` in the body core, closed **without its trigger having
  fired**, on the ground that the design was settled and the cost bounded. Every claim above held
  on re-derivation except one, and it is the one that mattered: the entry expected the first-token
  gap to be the longer of the two numbers, and on this deployment it is the shorter by an order of
  magnitude. The long silences (a delegated subtask waiting for admission and then running, a
  confirm card waiting on a person) can only happen once a turn is under way, so the mid-stream gap
  has to clear them while the first-event one only has to clear a swap and a first token. Both are
  **argued from budgets the brain ships rather than measured against an observed stall**, which
  nobody here has seen: 600 s from the swap's drain and load timeouts plus the resident stall
  ceiling, 7200 s from the subagent scheduler's admission wait plus the run deadline. The
  derivations, the twelve-mutation table, and what the body does when a gap fires (one
  `TransportError::Timeout`, because a silent end cannot settle the overlay's indicator and would
  claim a cancel the user never made) are in the ADR-0024 idle-gap addendum. One residue filed: the
  idle gap is a backstop rather than a useful bound until the brain owes a heartbeat on a long
  silent stretch ([R-421](421-a-silent-turn-owes-the-body-a-heartbeat.md)).
