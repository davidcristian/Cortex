# Two of the three readings the abandonment line distinguishes are only ever arranged

**Status:** open, actionable
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

That matters for the same reason the expiry row did. The claim is about grpc's behaviour, not
about arithmetic: a `grpc.aio` that answered `0` for a client that cancelled early, rather than the
positive remainder, would make an operator's three-way reading a two-way one, and every test in the
suite would stay green while the record and the module contract both went wrong.

**What it would take, and the one thing to check first.** A second wire case, a unary call with a
deadline long enough that the reading cannot be near it, cancelled by the client once the handler
has certainly been entered. The reading should then be a positive float close to the announced
window. The awkward half is the ordering, since a cancel that arrives before the handler runs
produces no line at all, and the fixture's never-answering store is what makes the wait for the
line deterministic. The `None` row is a different call again: a client that announces no deadline
and drops the channel, which is the shape the body never sends, so it may be honest to leave that
row as a rendering test and say so rather than build a third case for it.

**What would close it.** The positive reading observed over the wire, with the ordering made
deterministic rather than slept on, and a decided answer for the `None` row, whether that is a
third case or a written reason it stays a fake.

## Trail

- 2026-08-21: opened by the close of [R-346](346-a-clamped-reading-nothing-pins.md), which pinned
  the expiry reading over the wire and left the other two rows on values the file arranges.
