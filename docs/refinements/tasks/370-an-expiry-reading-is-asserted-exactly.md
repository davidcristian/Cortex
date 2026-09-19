# An abandonment case asserts an exact reading a loaded machine does not always produce

**Status:** done 2026-08-21
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)

The wire case in `packages/orchestrator/tests/test_abandon.py`,
`test_an_abandoned_unary_call_says_so_and_prints_the_time_it_had_left`, asserts three things about
the `time_remaining` a dropped call leaves on its log record: that it is not negative, that it is
well under the announced window, and that it is exactly `0`. The third is
what the module contract tells an operator to expect, and its comment records the evidence: 120
runs of the scenario, every one exactly `0` and an `int`, 100 of those with the whole repo check
running beside it.

It failed once anyway. On 2026-08-21 the case failed inside an unrelated set of mutations, one of
which was a one-character change to a comparison in `cortex_orchestrator/bounds.py`, a module that
touches no part of this path. The same mutation was run twice more and failed only the case it was
aimed at, so the reading is a load-sensitive flake. What made that run different is that a second
`pytest` process and several scans were sharing the machine with it.

`time_remaining` is grpc's own nonnegative float, the deadline minus now, clamped at zero. It reads
exactly `0` when the cancellation reaches the handler strictly after the announced 0.2 s window has
passed, which is the normal ordering. Under enough load the cancellation can be delivered while a
few microseconds of the window remain, and then the reading is a small positive float that
satisfies the other two assertions and fails this one.

Three ways to close it: widen the announced window, which makes the race rarer without removing it
and slows the case; assert the rendering instead, which is the same claim in a different place and
no more reliable; or assert `remaining == 0 or remaining < some tiny bound`, which is the accurate
reading of what the clamp guarantees and gives up the one thing the exact assertion buys, that an
expiry renders as an `int` rather than as `0.0`.

## History

- 2026-08-21: Filed by the close of [363](363-the-call-bound-and-the-run-bound-are-unordered.md),
  whose mutation run observed the failure and whose re-run of the same mutation is the evidence
  that it did not cause it.
- 2026-08-21: Fixed as the third option, the bound rather than a wider window or a rendering, after
  measuring the reading instead of arguing about it. Under 48 busy loops on a 24 core machine with
  a second full brain suite beside them: 32 of 200 replays of the scenario read a positive float
  rather than an integer zero (0.000017 s to 0.0073 s, median 0.0018 s), 5 of 30 runs of the case
  itself failed on `remaining == 0`, and one full run of the 2831 case brain suite failed this case
  alone with nothing mutated. Idle, 20 replays read `0` every time. So `remaining == 0` came out
  and the rendered tail beside it went with it, both having asserted the same non-deterministic
  reading; `remaining >= 0` and `remaining < _ANNOUNCED_S / 2` stay and are now the whole of what
  the wire case claims, and the rendering of an expiry stays asserted in the parameterized case
  that hands the wrapper its own `0`. The bound was left at half the window rather than tightened
  to the measured worst case, which would promote this machine's synthetic load to a rule. The
  prose that promised an exact zero was corrected in `abandon.py`'s module docstring and
  `docs/modules/brain-orchestrator.md`. Four constants in place of `context.time_remaining()`
  proved both surviving assertions able to fail, and the corrected case then ran 40 times under the
  same load without failing. It opened
  [R-371](371-a-floor-and-a-sliver-are-indistinguishable.md) and
  [R-372](372-the-sliver-is-unsampled-over-time.md).
