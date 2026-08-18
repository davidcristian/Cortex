# A turn stream that stalls has no bound at all

**Status:** open, fix when it bites
**Area:** seam-transport
**Trigger:** a turn observed stalling in real use, meaning the brain accepted the turn and then
sent nothing for long enough that the user gave up on the thinking indicator, rather than failing
it
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
