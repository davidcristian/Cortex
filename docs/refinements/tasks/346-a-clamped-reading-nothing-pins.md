# A clamped deadline reading is described in prose and asserted nowhere

**Status:** done 2026-08-21
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)

The test that drives a real expiry, in `brain/packages/orchestrator/tests/test_abandon.py`,
explained its assertion by saying grpc clamps the remaining time at zero rather than letting it go
negative, so the reading is exactly zero. What it asserted was `remaining < _ANNOUNCED_S / 2`,
which every reading below half the announced window satisfies, zero among them. The commit that added it made
the stronger claim in its body, that the reading arrives as an integer zero. Nothing in the suite
checked that.

So the file stated a fact about grpc's behaviour that it did not check. If grpc stopped clamping
and began reporting a small negative float, the prose would be wrong and the run would still pass.

The loose bound may still be right: the reading is a real clock, and a test that demands exactly
`0` fails on a scheduler hiccup rather than on a regression. That is an argument the file does not
make. Two ways to close it: assert what the prose claims, that the reading is not negative and is
zero once clamped, keeping the half-window bound as the loose half of the pair; or rewrite the
prose to say the reading is a clock that has run down rather than an exact zero.

## History

- 2026-08-20: Opened by a review of the abandonment line, which found the test's docstring naming a
  clamp that the assertion beneath it does not require.
- 2026-08-21: Fixed as the first of the two options, the clamp asserted rather than the prose
  relaxed, which this entry made conditional on the clamp being real. It is: the wire scenario was
  run 120 times before anything was asserted, in batches of 20 and 100, the second with all four
  trees of `just check` running beside it, and every reading was exactly `0` and an `int`. grpc
  documents the answer as a nonnegative float besides. The case now asserts `remaining >= 0`, keeps
  `remaining < _ANNOUNCED_S / 2` as the loose half of the pair, and adds `remaining == 0`. A second
  half the entry did not name came out with it: the last assertion interpolated the reading into
  the line it checked, so it could not say what a real expiry renders as, and it now writes
  `time_remaining=0` out. Three mutations of `abandon.py` proved all four able to fail, and all
  three passed the case as it stood before. It opened
  [R-351](351-two-readings-only-a-fake-ever-produced.md), the two rows of the reading table that
  only a fake has ever produced.
