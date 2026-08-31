# A clamped deadline reading is described in prose and pinned nowhere

**Status:** landed 2026-08-21
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Opened 2026-08-20 by a review of the abandonment interceptor. The test that drives a real expiry,
in `brain/packages/orchestrator/tests/test_abandon.py`, explains its assertion by saying grpc
clamps the remaining time at zero rather than letting it go negative, "so it lands there". What it
then asserts is `remaining < _ANNOUNCED_S / 2`, which every reading below half the announced window
satisfies, zero among them. The commit that landed it made the stronger claim in its body, that the
reading arrives as an integer zero. Nothing in the suite holds that.

So the file states a fact about grpc's behaviour that the file does not check, which is the shape
this repo treats as a defect in the other direction too: a comment that outruns its assertion is a
claim a future reader will trust without the suite ever having earned it. If grpc stopped clamping
and began reporting a small negative float, the prose would be wrong and the run would still pass.

**Why the loose bound may still be the right one.** The reading is a real clock, and a test that
demands exactly `0` is a test that fails on a scheduler hiccup rather than on a regression. That is
the real argument for the bound as written, and it is an argument the file does not make; what it
makes instead is an argument for a stricter assertion than it carries.

**What would close it.** Either assert what the prose claims, that the reading is not negative and
is zero once clamped, keeping the half window bound beside it as the loose half of the pair, or
rewrite the prose to say the reading is a clock that has run down rather than an exact zero, and
drop the sentence about where it lands. The first is two lines and is preferable if the clamp is
real, which is what the commit body already reports observing.

## Trail

- 2026-08-20: opened by a review of the abandonment line, which found the test's docstring naming a
  clamp that the assertion beneath it does not require.
- 2026-08-21: Landed as the first of the two closes this entry offered, the clamp asserted rather
  than the prose relaxed, which the entry made conditional on the clamp being real. It is: the wire
  scenario was run 120 times before anything was asserted, in batches of 20 and 100, the second with
  all four trees of `just check` running beside it, and every reading was exactly `0` and an `int`.
  grpc documents the answer as a nonnegative float besides. The case now asserts `remaining >= 0`,
  keeps `remaining < _ANNOUNCED_S / 2` as the loose half of the pair, and adds `remaining == 0`. A
  second half the entry did not name came out with it: the last assertion interpolated the reading
  into the line it checked, so it could not say what a real expiry renders as, and it now spells
  `time_remaining=0` out. Three mutations of `abandon.py` proved all four able to fail, and all
  three of them passed the case as it stood before. Recorded in the ADR-0024 addendum dated the
  same day, which also files what it opened:
  [R-351](351-two-readings-only-a-fake-ever-produced.md), the two rows of the reading table that
  only a fake has ever produced.
