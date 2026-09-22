# Two of the three readings the abandonment line separates come only from a fake

**Status:** done 2026-08-22
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)

`AbandonedCallInterceptor` prints `context.time_remaining()` and judges none of it, and the record
of that decision reads the number three ways: `0` is the announced deadline expiring, a positive
value is a caller that stopped waiting early, and `None` is a caller that announced no deadline at
all. Only one of the three is observed. In
`brain/packages/orchestrator/tests/test_abandon.py`, the only place the reading is real is the wire
case, and it drives an expiry. The other two are driven through `_Context`, a stand-in whose
`time_remaining()` answers whatever the parameters handed it, so those cases check the rendering of
a value nobody watched grpc produce.

The claim is about grpc's behaviour, not about arithmetic: a `grpc.aio` that answered `0` for a
client that cancelled early would turn an operator's three-way reading into a two-way one, and
every test would keep passing.

Closing it needs a second wire case, a unary call with a deadline long enough that the reading
cannot be near it, cancelled by the client once the handler has certainly been entered, giving a
positive float close to the announced window. The awkward half is ordering, since a cancel that
arrives before the handler runs produces no line at all.

## History

- 2026-08-21: Opened by the close of [R-346](346-a-clamped-deadline-reading-is-asserted-nowhere.md), which asserted
  the expiry reading over the wire and left the other two on values the file arranges.
- 2026-08-22: Fixed, and larger than the entry proposed. Both missing readings got a wire case, not
  one: a caller that stops early (announce wide, wait on the handler's own entered event, cancel)
  and a caller that announces no deadline and drops the call. The `None` case was not left as a
  rendering test with a written reason, and the entry's argument for that option is the part that
  did not survive: it is not a claim about what the body sends, it is a claim about what grpc
  answers for a call with no deadline, and a grpc that folded that into a `0` would cost an
  operator a whole reading with the suite still passing. The ordering is a fact rather than a wait:
  the never-answering store sets an `asyncio.Event` from inside the handler and the fixture hands
  it out, so nothing sleeps to order two events. Decided together with
  [R-371](371-a-floor-and-a-sliver-are-indistinguishable.md), which added the fourth wire case for
  the floor, and [R-372](372-the-sliver-is-unsampled-over-time.md), which those two between them
  made a decline. Opened [R-381](381-the-header-encoding-error-is-larger-than-recorded.md).
