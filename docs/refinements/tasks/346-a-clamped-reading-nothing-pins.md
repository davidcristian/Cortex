# A clamped deadline reading is described in prose and pinned nowhere

**Status:** open, actionable
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
and began reporting a small negative float, the prose would be wrong and the run would stay green.

**Why the loose bound may still be the right one.** The reading is a real clock, and a test that
demands exactly `0` is a test that fails on a scheduler hiccup rather than on a regression. That is
the honest argument for the bound as written, and it is an argument the file does not make; what it
makes instead is an argument for a stricter assertion than it carries.

**What would close it.** Either assert what the prose claims, that the reading is not negative and
is zero once clamped, keeping the half window bound beside it as the loose half of the pair, or
rewrite the prose to say the reading is a clock that has run down rather than an exact zero, and
drop the sentence about where it lands. The first is two lines and is preferable if the clamp is
real, which is what the commit body already reports observing.

## Trail

- 2026-08-20: opened by a review of the abandonment line, which found the test's docstring naming a
  clamp that the assertion beneath it does not require.
