# The margin under the expiry bound was measured once and is sampled by nothing

**Status:** open, actionable
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

The wire expiry case in `brain/packages/orchestrator/tests/test_abandon.py` asserts
`remaining < _ANNOUNCED_S / 2`, a bound of 0.1 s against an announced window of 0.2 s. The reason
it is 0.1 and not 0.01 is a single measurement: with 48 busy loops on a 24 core machine and a
second full brain suite running beside them, the widest sliver in 200 replays was 0.0073 s. That
is a thirteenfold margin, and it was chosen deliberately over tightening the bound to the observed
worst case, which would promote one machine's synthetic load to a suite-wide invariant.

The judgement is defensible and it is also unwatched. Nothing samples that margin again. A slower
CI runner, a busier developer box, or a grpc release that delivers cancellations differently could
walk the sliver up toward 0.1 s, and the first anyone would learn of it is this case reddening,
which is the failure mode the exact assertion was replaced to avoid. The number that would tell
anyone in advance, the widest reading seen across many runs, is produced by every run of the case
and kept by none of them.

**What would close it.** Cheapest first, and none of these is obviously the right size:

- Have `just shuffle`, the weekly sweep that gates nothing, drive this scenario repeatedly and
  print the distribution. It already exists as the place for a measurement nobody's commit waits
  on, and a sweep is a better home for a sample than a gate is.
- Or leave the gate alone and record a periodic reading, in the shape the turn-cost measurement
  uses, so the margin is a number somebody can compare against the last one.
- Or decide the margin needs no watching, because the claim the bound makes ("the announced window
  ran down") tolerates any sliver well under the window, and the only thing a growing sliver would
  cost is the distinction filed as
  [371](371-a-floor-and-a-sliver-are-indistinguishable.md). That is a legitimate close and would
  be a decline.

Deliberately last of the three in cost order, because the third may be the answer.

## Trail

- 2026-08-21: Filed by the close of
  [370](370-an-expiry-reading-is-asserted-exactly.md), whose measurement chose the bound's margin
  and left nothing sampling it. Recorded in the ADR-0024 addendum dated the same day.
