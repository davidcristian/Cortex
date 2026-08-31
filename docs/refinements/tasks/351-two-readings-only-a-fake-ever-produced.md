# Two of the three readings the abandonment line distinguishes are only ever arranged

**Status:** landed 2026-08-22
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Opened 2026-08-21 by the close of [R-346](346-a-clamped-reading-nothing-pins.md), which asserted the
expiry reading over the wire and, in doing so, made the asymmetry beside it visible.

`AbandonedCallInterceptor` prints `context.time_remaining()` and judges none of it, and the record
of that decision reads the number three ways: `0` is the announced deadline expiring, a positive
value is a caller that stopped waiting early, and `None` is a caller that announced no deadline at
all. One of the three is now observed. In
`brain/packages/orchestrator/tests/test_abandon.py`, the only place the reading is real is the wire
case, and it drives an expiry. The other two rows are driven through `_Context`, a stand-in whose
`time_remaining()` answers whatever the parameterization handed it, so what those cases pin is the
rendering of a value nobody watched grpc produce.

That matters for the same reason the expiry row did. The claim is about grpc's behaviour, not about
arithmetic: a `grpc.aio` that answered `0` for a client that cancelled early, rather than the
positive remainder, would make an operator's three-way reading a two-way one, and every test in the
suite would keep passing while the record and the module contract both went wrong.

**What it would take, and the one thing to check first.** A second wire case, a unary call with a
deadline long enough that the reading cannot be near it, cancelled by the client once the handler
has certainly been entered. The reading should then be a positive float close to the announced
window. The awkward half is the ordering, since a cancel that arrives before the handler runs
produces no line at all, and the fixture's never-answering store is what makes the wait for the line
deterministic. The `None` row is a different call again: a client that announces no deadline and
drops the channel, which is the shape the body never sends, so it may be defensible to leave that
row as a rendering test and say so rather than build a third case for it.

**What would close it.** The positive reading observed over the wire, with the ordering made
deterministic rather than slept on, and a decided answer for the `None` row, whether that is a
third case or a written reason it stays a fake.

## Trail

- 2026-08-21: opened by the close of [R-346](346-a-clamped-reading-nothing-pins.md), which pinned
  the expiry reading over the wire and left the other two rows on values the file arranges.
- 2026-08-22: Landed, and larger than the entry proposed. Both missing readings got a wire case, not
  one: a caller that stops early (announce wide, wait on the handler's own entered event, cancel)
  and a caller that announces no deadline and drops the call. The `None` row was **not** left as a
  rendering with a written excuse, and the entry's reasoning for that option is the part that did
  not survive: the row is not a claim about what the body sends, it is a claim about what grpc
  answers for a call with no deadline, and a grpc that folded that into a `0` would cost an operator
  a whole reading with the suite still passing. The ordering is a fact rather than a wait, as the
  entry asked: the never-answering store sets an `asyncio.Event` from inside the handler and the
  fixture hands it out, so nothing sleeps to order two events. Decided together with
  [R-371](371-a-floor-and-a-sliver-are-indistinguishable.md), which added the fourth wire case that
  pins the floor, and [R-372](372-the-sliver-is-unsampled-over-time.md), which those two between
  them made a decline. Opened [R-381](381-the-header-encoding-error-is-larger-than-recorded.md).
  Recorded in the ADR-0024 addendum dated the same day.
