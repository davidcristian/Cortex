# A row named before its keep verb is deleted

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-14

`parts` (`forget_clauses.py`) reads a clause asking to keep from its keep verb onward, so the words
before the verb stay in the part asking to forget
([the keep clause reader](../../readings/forget-keep-clause.md)). When a clause names the row first
and the keep verb follows, the row is listed and deleted. With the rows `meine Karte ist 4111 1111
1111 4242` and `mein Handy ist 0721 555 4242` and the call text `4242`, `Vergiss die Karte 4242,
mein Handy bleibt.` and `Vergiss die Karte 4242, das Handy bleibt.` list and delete both rows, and
so does `Forget the card 4242, my phone I keep.` with the English rows. German puts the verb after
the subject in this clause, so the form is common there. The card lists the phone before the
delete, so the person can deny it; a delete the person asked against is the unsafe direction.

## What to do

1. Write tests first from the messages above, and near misses that ask to forget the row named
   before a forget verb (`mein Handy vergiss auch`).
2. Read a keep verb ending a clause as asking to keep the whole clause, when no forget verb is in
   it, rather than from the verb onward. Keep rows when unsure.
3. Replay every recorded message and test string through the card; name every changed listing.

## History

- 2026-11-14: filed while closing the adding clause tasks 1187 and 1192, from `probe.py` and
  `c2.json` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/11450320-079c-401d-9f26-43a763a369b6/scratchpad/slot3/`.
