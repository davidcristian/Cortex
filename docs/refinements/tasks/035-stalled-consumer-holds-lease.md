# A stalled consumer holds the GPU lease

**Status:** open, fix when it bites
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** a deployment with more than one live consumer, or any report of one slow client stalling turns that are not its own; at one overlay on one machine there is one consumer and it reads as fast as it can.

The reply's lease is held for the adapter generator's whole lifetime, and
the credit bound above (`CORTEX_SEAM_CONVERSE_BUFFER`) suspends generation INSIDE that lease when
the consumer stops dequeuing, so a stalled reader does not merely stall itself. Measured on the
run above at a one-credit bound with the reader stalling 12 s: the stalled stream's reply held
the lease **16.52 s** against the 2.2 s to 3.6 s an unstalled reply holds it, and the next
stream's **fold waited 16.51 s** behind it. This predates the summary and is not caused by it;
what the default-on fold changes is who pays, since a fold is now among the things that queue.
Neither obvious direction is free: the bound exists to cap a stalled stream's memory (the entry
that landed it is above), and letting generation run ahead of the consumer to release the lease
sooner is the exact thing that bound prevents. A real fix is likelier to be a bound on how long a
suspended generation may hold the lease, which means the adapter abandoning a stream the
seam is no longer draining, and that is a port-shaped change rather than a knob.

## Trail

- 2026-08-08: Opened by the fold-under-load run on its way past, as the shipped backpressure
  behaving as designed with nobody having written down who pays for it.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing, recording that what remains open there is live-observation shaped, its trigger being a
  deployment doing something rather than a file saying something.
