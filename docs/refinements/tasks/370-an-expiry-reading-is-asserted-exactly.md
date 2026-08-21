# An abandonment case asserts an exact reading a loaded machine does not always produce

**Status:** open, actionable
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
