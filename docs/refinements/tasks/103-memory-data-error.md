# A malformed row degrades as an outage

**Status:** landed 2026-08-11
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The line the close drew is
that a port's declared failure may degrade and anything else is a defect that must propagate,
and it delegated the drawing of it to the adapters, on the argument that they wrap a backend
that could not be reached and wrap nothing else. That argument is true of `_WRAPPED` and false
of the second `except` in `PgVectorMemoryStore.search` and `count_candidates`, which wrap
`(KeyError, IndexError, TypeError, ValueError)` from a malformed row or an unreadable total into
the same `MemoryStoreError`. A corrupt row therefore reaches a turn as an outage and costs it
its notes quietly rather than failing loudly, which is exactly the swallowing the close said it
would not do. It is visible (the `warning` carries the traceback and the adapter's own
"malformed memory row in search result"), so this is a sharpening rather than a hole. The shape
is the `ModelNotHostedError` precedent: a subclass of `MemoryStoreError` for the data failures,
so every existing `except MemoryStoreError` keeps catching it, plus a narrower `except` ahead of
the degrading one in the two core catches. **Trigger:** the first malformed row anybody actually
meets, or the next port to draw this same line, since the rule wants to be one rule.

**Closed 2026-08-11**, hours after it opened and **ahead of its trigger, neither arm of which
fired**: no malformed row was met and no other port drew this line. What moved it is that the
two closes on either side of it had, between them, made a data defect indistinguishable from an
outage on purpose, one degrading a turn on the port's declared error and the next pinning that
every implementation raises it, so the swallowing this entry named was not a possibility but the
shipped behaviour. It landed as the entry specified, which is the second time the
`ModelNotHostedError` shape has been cheaper than inventing one: `MemoryDataError` subclasses
`MemoryStoreError`, so every existing catch is unchanged, the adapter raises it from its three
decoding catches and from nothing else, and `_recalled_context` names it ahead of the degrading
catch and re-raises it.

The decision the entry left open was what the core should do with the narrower error, and the
answer is that the read fails rather than degrading more loudly. The criterion is whether the
condition heals without anybody touching the deployment: a stopped server comes back and every
turn degraded meanwhile was a bridge, while a row that will not decode decodes no better next
week, so degrading around it buys a permanent thinness nobody chose. Logging it at a level that
reaches somebody was the alternative and it was refused on the previous close's own words, that
a failure only a log records is the silence the degradation was written to end. The user-facing
half landed that same day is untouched, and that is part of the argument rather than a casualty
of it: the `forgoing` status says this turn is answered without earlier notes, which is a false
sentence about a turn that is not going to answer, so a data defect emits none.

**The adapter can genuinely tell the two apart at the point it wraps**, which is what kept this
small, and the answer is not a judgement call: the conditions arrive as disjoint exception
types, asyncpg's `PostgresError`, `InterfaceError` and `OSError` for a machine that could not
answer against a `KeyError` or `ValueError` out of `_to_scored` for an answer this code could
not read. Two edges are recorded rather than left to be found. An aggregate returning no row
reaches `count_candidates` as an `IndexError` and is classified as data, correctly, the server
having answered; and an embedding the core hands `search` that will not render as a literal is
classified as data too, `_to_literal` sitting inside the `try`, which is our own bad value and
so the same side of the line as the table's. The shared list holds only the half both
implementations can answer, that a gone backend must not arrive as the subclass, since the
in-memory twin decodes nothing and a scripted data defect would be a check asserting on its own
scripting; `test_pgvector.py` holds the other half where the rows are. Proven able to fail
before it was trusted, in both directions: a store scripted to call an outage a data defect
reddens the shared check, and removing the core's re-raise reddens its test, the degrading catch
swallowing the subclass. Both breaks restored ([ADR-0008](../../adr/ADR-0008-memory-v1.md)
data-defect addendum). **One opened in its place**, the next entry here.

## Trail

- 2026-08-11: Opened by the unavailable-memory close as residue of it rather than as anything found
  beside it, and filed fix when it bites.
- 2026-08-11: Closed the same day, hours after it opened and ahead of a trigger neither arm of which
  fired, so the area's count held at 8 by exchange rather than by standing still. What moved it is
  that the two closes on either side had between them made a data defect indistinguishable from an
  outage on purpose, so the swallowing this entry named was the shipped behaviour rather than a
  possibility. It opened one in its place, the delete cascade's seam mapping.
