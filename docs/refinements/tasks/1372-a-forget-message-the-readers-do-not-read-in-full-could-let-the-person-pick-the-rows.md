# A forget message the readers do not read in full could let the person pick the rows

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7
**Verified:** 2026-11-26
**Trigger:** a History line in this file recording the user's pick of the design and of the card's look.

The typed readers of a forget message are frozen, and the forms they leave unread are recorded
with their counts
([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)). On such
a form the readers still decide which rows the card lists: some forms list a row the message asks
to keep, which the person must notice and decline, and others keep a row the message asks to
delete.

This is a proposal, not a build. When the readers cannot account for every word of a forget
message, the card would list every row that holds the value with none selected, and the person
picks the rows to delete. No unread form then decides a row: a row is deleted only when the
person selects it, and a row asked to delete is never kept without being shown.

## What it needs

1. A typed test of whether the readers account for every word of the message, built from what
   the readers already return and adding no word list. Its safe direction shows the rows with
   none selected.
2. A pick per row. `ConfirmResponse` in [proto/body.proto](../../../proto/body.proto) holds only
   `approved` today, so the answer needs a field naming the picked rows, and `invoke` deletes
   only those of the ids the tool kept for the call (`delete_ids`, decision 1).
3. The user's picks: whether the card selects nothing or shows the readers' choice for the person
   to change, the look of a row that is not selected, and the card's wording.

## History

- 2026-11-26: filed with the freeze of the forget message readers as the one structural
  alternative to widening them; it waits on the user's pick.
