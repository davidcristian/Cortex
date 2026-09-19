# A malformed row degrades as an outage

**Status:** done 2026-08-11
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The degradation close ([R-102](102-unavailable-memory-degradation.md)) decided that a port's
declared failure may degrade and anything else must propagate, and left the adapters to draw
that boundary, on the reasoning that they wrap a backend that could not be reached and nothing
else. That is true of `_WRAPPED` and false of the second `except` in `PgVectorMemoryStore.search`
and `count_candidates`, which wrap `(KeyError, IndexError, TypeError, ValueError)` from a
malformed row or an unreadable total into the same `MemoryStoreError`. A corrupt row therefore
reached a turn as an outage, costing it its notes without reporting a failure.

**Closed 2026-08-11**, hours after it opened and ahead of its trigger, because the two closes on
either side of it had between them made a data defect indistinguishable from an outage on
purpose, so this was the shipped behaviour rather than a possibility.

`MemoryDataError` subclasses `MemoryStoreError`, so every existing catch is unchanged. The
adapter raises it from its three decoding catches and from nothing else, and `_recalled_context`
names it ahead of the degrading catch and re-raises it. The read therefore fails rather than
degrading. The criterion is whether the condition fixes itself without anybody touching the
deployment: a stopped server comes back, and every turn degraded meanwhile covered the gap, while
a row that will not decode decodes no better next week, so degrading around it would buy a
permanent thinness nobody chose. Logging it at a level that reaches somebody was the alternative
and was refused, a failure only a log records being the silence the degradation was written to
end. The `forgoing` status is not emitted for a data defect, because it says this turn is
answered without earlier notes, which is false about a turn that is not going to answer.

The adapter can tell the two apart where it wraps them, because they arrive as disjoint exception
types: asyncpg's `PostgresError`, `InterfaceError` and `OSError` for a machine that could not
answer, against a `KeyError` or `ValueError` out of `_to_scored` for an answer this code could not
read. Two edges are recorded rather than left to be found. An aggregate returning no row reaches
`count_candidates` as an `IndexError` and is classified as data, correctly, since the server
answered. An embedding the core hands `search` that will not render as a literal is classified as
data too, because `_to_literal` runs inside the `try`, and our own bad value belongs on the same
side of the boundary as the table's.

The shared check list holds only the half both implementations can answer, that a gone backend
must not arrive as the subclass, since the in-memory twin decodes nothing; `test_pgvector.py`
holds the other half where the rows are. Proved able to fail in both directions before it was
trusted: a store scripted to call an outage a data defect fails the shared check, and removing
the core's re-raise fails its test, the degrading catch swallowing the subclass. Both breaks were
restored ([ADR-0008](../../adr/ADR-0008-memory-v1.md) decision 13).

## History

- 2026-08-11: Opened by the unavailable-memory close as residue of it, and filed as waiting for
  its trigger.
- 2026-08-11: Closed the same day, ahead of a trigger that had not fired, so the area's count
  held at 8 because one entry closed as another opened. It opened
  [R-104](104-delete-cascade-seam-mapping.md) in its place.
