# A stalled consumer holds the GPU lease

**Status:** open, fix when it bites
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** a deployment with more than one live consumer, or any report of one slow client stalling turns that are not its own; at one overlay on one machine there is one consumer and it reads as fast as it can.
**Verified:** 2026-09-11

The reply's lease is held for the adapter generator's whole lifetime, and
the credit bound ([028](028-converse-queue-backpressure.md), `CORTEX_SEAM_CONVERSE_BUFFER`) suspends generation INSIDE that lease when
the consumer stops dequeuing, so a stalled reader does not merely stall itself. Measured on the
[fold-under-load run](../../adr/ADR-0038-ranked-recall.md#fold-under-load-addendum-2026-08-08-the-sequencing-argument-measured-against-overlapping-streams)
at a one-credit bound with the reader stalling 12 s: the stalled stream's reply held
the lease **16.52 s** against the 2.2 s to 3.6 s an unstalled reply holds it, and the next
stream's **fold waited 16.51 s** behind it. This predates the summary ([027](027-session-history-summarization.md)) and is not caused by it;
what the default-on fold changes is who pays, since a fold is now among the things that queue.
Neither obvious direction is free: the bound exists to cap a stalled stream's memory (the entry
that landed it is [028](028-converse-queue-backpressure.md)), and letting generation run ahead of the consumer to release the lease
sooner is the exact thing that bound prevents. A real fix is likelier to be a bound on how long a
suspended generation may hold the lease, which means the adapter abandoning a stream the
seam is no longer draining, and that is a port-shaped change rather than a knob.

## Trail

- 2026-08-08: Opened by the fold-under-load run on its way past, as the shipped backpressure
  behaving as designed with nobody having written down who pays for it.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing, recording that what remains open there is live-observation shaped, its trigger being a
  deployment doing something rather than a file saying something.
- 2026-09-11: read against the tree and not fired. The mechanism is as described and nothing bounds
  it yet: `ConverseStream` in `converse_stream.py` still takes one credit per event from an
  `asyncio.Semaphore(max_buffered_events)`, and `LlamaCppBackend.stream` still yields each event
  from inside `async with self._manager.acquire(model)` (`backend.py`), so a consumer that stops
  dequeuing suspends the generator with the lease held; the only timeout in the stream module is
  the confirm timeout. The nearest thing to the abandonment the body proposes is `abandon.py`, the
  unary-call abandonment log of 2026-08-20, whose own docstring says `Converse` announces no
  deadline and must keep announcing none, so it stops exactly short of this entry. The shipped
  stack still has one overlay as its one consumer and the tree records no report of one client
  stalling another's turn. The three references to entries `above` in the old area doc now name
  their tasks, and the run the readings came from is linked.
