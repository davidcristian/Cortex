# A grpc that stopped flooring the reading is no longer told from one that did

**Status:** landed 2026-08-22
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

The abandonment line prints `context.time_remaining()` and judges none of it, so what the suite
holds is the only thing standing between the module's account of that reading and a grpc release
that quietly changes it. Since the expiry case became a bound rather than a point, one half of
that account is unheld.

The wire case in `brain/packages/orchestrator/tests/test_abandon.py` now asserts that a real expiry
reading is not negative and is under half the announced window. Both survive a grpc that stopped
flooring the reading at zero and began reporting the unspent sliver instead, because a real expiry
under load already reads as a sliver: the two are the same number. The mutation that stands in for
that release, a constant `0.05` in place of the reading, makes three cases fail, and all three are
the parameterized renderings, which fail on any constant at all because a constant is what they
vary. None of them is evidence about grpc. The same is true of a release that floors to a float
`0.0` rather than to an `int`.

What was given up is real but was also never as strong as it looked: before the bound, the wire
case caught those two by demanding an exact `0`, and that demand was itself unsound, failing on
about one run in six with the machine saturated.

**What would close it.** Something that separates the floor from the sliver without depending on
which one this run produced. Two shapes worth weighing, neither obviously right:

- Drive the scenario more than once inside the case and assert over the readings together, for
  instance that at least one of N is the integer floor. That is a real distinction (a grpc
  reporting the sliver would never produce the `int`) but it buys it with N loopback round trips
  and a flake of its own at whatever N leaves too little margin.
- Assert the floor where it can be made to happen rather than waited for: a case that lets the
  deadline pass by a wide margin before the cancellation is delivered, so the subtraction is
  already deeply negative. The obstacle is that nothing in the case chooses when grpc delivers
  the cancellation, which is exactly what made the original assertion flake.

Not urgent. It protects against a grpc change nobody has seen, and the module's own prose no longer
claims more than the suite holds, which is the failure mode this repo actually treats as a defect.

## Trail

- 2026-08-21: Filed by the close of
  [370](370-an-expiry-reading-is-asserted-exactly.md), which measured the expiry reading under load
  and replaced the exact assertion with a bound. Recorded in the ADR-0024 addendum dated the same
  day.
- 2026-08-22: Landed, by a shape this entry did not weigh. Neither of the two it offered was
  taken. Driving the scenario N times and asserting one reading is the integer floor buys the
  distinction probabilistically, and 51 of 400 saturated replays were slivers, so a run of N of
  them is not impossible at any N a suite can afford; forcing a deeply negative subtraction by
  withholding the event loop does work and was tried, but pays suite time to outrun a second clock
  rather than removing it. The case landed instead announces the deadline in `grpc-timeout`
  metadata with no `timeout=` beside it, so the only clock that can end the call is the brain's
  own, which cannot fire before it is due; 200 replays under saturation read an integer `0` every
  time. It asserts `isinstance(remaining, int)`, which separates the floor from the sliver by type
  rather than by value, and that is the assertion the `0.05` and `0.0` mutations now die to over
  the wire, having previously died only in the renderings. It is also the deployed shape of an
  expiry: the body killed or the connection half-opened, its cancellation never arriving. Decided
  together with [R-351](351-two-readings-only-a-fake-ever-produced.md), whose other two wire cases
  it sits beside, and [R-372](372-the-sliver-is-unsampled-over-time.md), which this close is the
  reason to decline. Recorded in the ADR-0024 addendum dated the same day.
