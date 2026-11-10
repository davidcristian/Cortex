# A forget keeping only longer values withholds a request to remember

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-10

`memory_withheld` (`memory_claim.py`) stores a turn whose message asks to remember when every
`forget_memories` call of it matched nothing (`_unmatched_keep`), since a forget of a value never
stored deletes nothing. A call whose every match holds its text only inside a longer value returns
`INSIDE_ALL` with `matched_nothing` unset, so it deletes nothing too and still withholds the turn.
Unit reproduction, with only `User: Remember that my phone account is 015 123 456 7890.` stored and
the message `My phone is 015 123 456 789, remember it.`:

| Call text | Result | Turn withheld |
| --- | --- | --- |
| `0151 2345 6789` | the no-match result, `matched_nothing` set | no |
| `015 123 456 789` | `INSIDE_ALL` | yes |

A remember turn calling `forget_memories` was drawn once on 2026-11-10 (flow j of
[the readings](../../readings/forget-value-short-groups.md), its third seed); that call matched a
row and deleted it. `UNKEPT_CLAIM_NOTE` follows a reply claiming the fact was kept, so the person
is told.

## What to do

1. Draw a remember message beside a longer stored value 8 times through the proxy, counting the
   turns that call `forget_memories` with a text only the longer value holds, before deciding.
2. If the form occurs, weigh counting an `INSIDE_ALL` call with the unmatched ones in
   `_unmatched_keep` only. The store decision is a do-not-keep reader whose safe side is to
   withhold, so a message that also asks not to keep must stay withheld, and the no-match note
   must still not follow `INSIDE_ALL`.

## History

- 2026-11-10: filed from the audit of the text match change to the forget card.
