# The suite no longer separates a grpc that floors the reading from one that does not

**Status:** done 2026-08-22
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)

The abandonment line prints `context.time_remaining()` and judges none of it, so the suite is the
only thing between the module's account of that reading and a grpc release that changes it. Since
the expiry case became a bound rather than an exact value, one half of that account is unchecked.

The wire case in `brain/packages/orchestrator/tests/test_abandon.py` asserts that a real expiry
reading is not negative and is under half the announced window. Both survive a grpc that stopped
clamping the reading at zero and began reporting the unspent remainder instead, because a real
expiry under load already reads as a small remainder: the two are the same number. The mutation
that stands in for that release, a constant `0.05` in place of the reading, makes three cases fail,
and all three are the parameterized renderings, which fail on any constant at all. The same is true
of a release that clamps to a float `0.0` rather than to an `int`.

What was given up was never as strong as it looked: before the bound, the wire case caught those
two by demanding an exact `0`, and that demand failed on about one run in six with the machine
saturated.

Closing it needs something that separates the clamp from the remainder without depending on which
one this run produced. Two options, neither obviously right: drive the scenario more than once
inside the case and assert that at least one of N readings is the integer zero, which is a real
distinction bought with N loopback round trips and a flake of its own; or let the deadline pass by
a wide margin before the cancellation is delivered, so the subtraction is already deeply negative,
which nothing in the case can arrange.

## History

- 2026-08-21: Filed by the close of [370](370-an-expiry-reading-is-asserted-exactly.md), which
  measured the expiry reading under load and replaced the exact assertion with a bound.
- 2026-08-22: Fixed, by an option this entry did not weigh. Driving the scenario N times and
  asserting one reading is the integer zero buys the distinction only by probability, and 51 of 400
  saturated replays were remainders, so a run of N of them is not impossible at any N a suite can
  afford; forcing a deeply negative subtraction by withholding the event loop does work and was
  tried, but pays suite time to outrun a second clock rather than removing it. The case built
  instead announces the deadline in `grpc-timeout` metadata with no `timeout=` beside it, so the
  only clock that can end the call is the brain's own, which cannot fire before it is due; 200
  replays under saturation read an integer `0` every time. It asserts `isinstance(remaining, int)`,
  which separates the two by type rather than by value, and that is the assertion the `0.05` and
  `0.0` mutations now fail over the wire, having previously failed only in the renderings. It is
  also the deployed form of an expiry: the body killed or the connection half-open, its
  cancellation never arriving. Decided together with
  [R-351](351-two-readings-only-a-fake-ever-produced.md), whose other two wire cases it sits
  beside, and [R-372](372-the-sliver-is-unsampled-over-time.md), which this close is the reason to
  decline.
