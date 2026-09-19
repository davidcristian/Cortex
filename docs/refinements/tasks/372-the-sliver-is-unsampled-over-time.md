# The margin under the expiry bound was measured once and is sampled by nothing

**Status:** declined 2026-08-22
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)

The wire expiry case in `brain/packages/orchestrator/tests/test_abandon.py` asserts
`remaining < _ANNOUNCED_S / 2`, a bound of 0.1 s against an announced window of 0.2 s. The reason
it is 0.1 and not 0.01 is a single measurement: with 48 busy loops on a 24 core machine and a
second full brain suite running beside them, the widest remainder in 200 replays was 0.0073 s. That
is a thirteenfold margin, chosen over tightening the bound to the observed worst case, which would
promote one machine's synthetic load to a suite-wide rule.

Nothing samples that margin again. A slower CI runner, a busier developer box, or a grpc release
that delivers cancellations differently could walk the remainder up toward 0.1 s, and the first
anyone would learn of it is this case failing. The number that would give warning, the widest
reading seen across many runs, is produced by every run of the case and kept by none.

Three possible endings, in cost order: have `just shuffle`, the weekly pass that checks nothing,
drive this scenario repeatedly and print the distribution; record a periodic reading in the shape
the turn-cost measurement uses; or decide the margin needs no watching, because the claim the bound
makes tolerates any remainder well under the window, and the only thing a growing remainder would
cost is the distinction filed as [371](371-a-floor-and-a-sliver-are-indistinguishable.md).

## History

- 2026-08-21: Filed by the close of [370](370-an-expiry-reading-is-asserted-exactly.md), whose
  measurement chose the bound's margin and left nothing sampling it.
- 2026-08-22: Declined, on this entry's own third option, and the reason is what
  [R-371](371-a-floor-and-a-sliver-are-indistinguishable.md) built rather than that watching is
  awkward. The margin was worth watching because a growing remainder would eventually fail the
  half-window bound, and the bound's only remaining value was telling the clamp from the remainder;
  that distinction now lives in a case where the remainder cannot occur at all. Neither sampling
  option was taken: both would sample a number whose upper bound is already enforced by the case's
  own precondition, since a remainder is bounded by the call setup this scenario must complete
  before the handler is entered, and a remainder approaching half the announced window means setup
  taking half the announced window, at which point no line is written and the case fails on the
  latch timing out. What is not claimed is that the margin cannot narrow, because it did: 400
  saturated replays here read a widest remainder of 0.0107 s against the 0.0073 s this entry
  recorded, taking the margin under the 0.1 s bound from thirteenfold to nine and a half. The bound
  is unchanged. See also [R-351](351-two-readings-only-a-fake-ever-produced.md), decided in the
  same pass, and [R-381](381-the-header-encoding-error-is-larger-than-recorded.md), which that
  measurement opened.
