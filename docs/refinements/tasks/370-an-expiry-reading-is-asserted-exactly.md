# An abandonment case asserts an exact reading a loaded machine does not always produce

**Status:** landed 2026-08-21
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

`packages/orchestrator/tests/test_abandon.py::test_an_abandoned_unary_call_says_so_and_prints_the_time_it_had_left`
asserts three things about the `time_remaining` a dropped call leaves on its log record: that it is
not negative, that it is well under the announced window, and that it is **exactly** `0`. The third
is what the module contract tells an operator to expect, and its comment records the evidence
honestly: 120 runs of the scenario, every one of them exactly `0` and an `int`, 100 of those with
the whole repo gate running beside it.

It failed once anyway. On 2026-08-21 the case reddened inside an unrelated mutation sweep, one arm
of which was a one-character change to a comparison in `cortex_orchestrator/bounds.py`, a module
that touch no part of this path. The same arm was run twice more, once before that sweep and once
after, and reddened only the case the mutation was aimed at both times, so the reading is a
load-sensitive flake and not a consequence of anything the sweep changed. What made that run
different is that a second `pytest` process and several gate scans were sharing the machine with
it.

The failure mode is worth stating precisely, because the assertion is defensible and the flake is
still real. `time_remaining` is `grpc`'s own nonnegative float, the deadline minus now, clamped at
zero. It reads exactly `0` when the cancellation reaches the handler strictly **after** the
announced 0.2 s window has passed, which is the normal ordering. Under enough load the
cancellation can be delivered while a few microseconds of the window remain, and then the reading
is a small positive float that satisfies the other two assertions and fails this one.

So the choice is between three things, and it wants deciding rather than defaulting:

- widen the announced window, which makes the race rarer without removing it, and slows the case;
- assert the **rendering** instead (the line already ends `time_remaining=0`, which a small float
  would not produce either), which is the same claim in a different place and no more robust;
- assert `remaining == 0 or remaining < some tiny bound`, which is the honest reading of what the
  clamp guarantees and gives up the one thing the exact assertion buys, that an expiry renders as
  an `int` rather than as `0.0`.

Nothing here is urgent: one failure in three runs of one arm, under a load the gate does not
normally produce. It is filed because a flake nobody wrote down is rediscovered from scratch by
whoever next sees a red run they cannot explain.

## Trail

- 2026-08-21: Filed by the close of
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md), whose mutation sweep observed the
  failure and whose re-run of the same arm is the evidence that the mutation did not cause it.
- 2026-08-21: Landed as the third of the three choices this entry offered, the bound rather than a
  wider window or a rendering, after measuring the reading instead of arguing about it. Under 48
  busy loops on a 24 core machine with a second full brain suite beside them: 32 of 200 replays of
  the scenario read a positive float rather than an integer zero (0.000017 s to 0.0073 s, median
  0.0018 s), 5 of 30 runs of the case itself reddened on `remaining == 0`, and one full run of the
  2831 case brain suite reddened this case alone, with nothing mutated, which is the original
  observation reproduced. Idle, 20 replays read `0` every time. So `remaining == 0` came out and
  the rendered tail beside it went with it, both having pinned the same non-deterministic reading;
  `remaining >= 0` and `remaining < _ANNOUNCED_S / 2` stay and are now the whole of what the wire
  case claims, and the rendering of an expiry stays pinned in the parameterized case that hands
  the wrap its own `0`. The bound was left at half the window rather than tightened to the
  measured worst case, which would be this machine's synthetic load promoted to an invariant. The
  prose that promised an exact zero was corrected in four places: `abandon.py`'s module docstring,
  `docs/modules/brain-orchestrator.md`, the reading table and the wire paragraph in the ADR-0024
  abandonment addendum, and the head of the addendum from earlier the same day that asserted it.
  Four constants in place of `context.time_remaining()` proved both surviving assertions able to
  fail, and the corrected case then ran 40 times under the same load without reddening. Recorded
  in the ADR-0024 addendum dated the same day, which also files what it opened:
  [R-371](371-a-floor-and-a-sliver-are-indistinguishable.md) and
  [R-372](372-the-sliver-is-unsampled-over-time.md).
