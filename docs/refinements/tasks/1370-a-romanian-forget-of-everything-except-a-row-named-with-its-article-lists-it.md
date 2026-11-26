# A Romanian forget of everything except a row named with its article lists it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`Uită tot în afară de dulapul.` deletes the locker it asks to keep for the call text `dulap`, alone
and after another forget clause (`Uită cardul meu. Uită tot în afară de dulapul.`), at the second
audit's commit `1c7c329cf` and at the tree after the head read after another forget clause. The row
holds `dulap` and the message says `dulapul`, so no reader reads the excepted word as naming the
row ([task 1282](1282-a-romanian-row-named-with-its-article-outside-a-keep-clause-names-no-row.md)),
and `tot` is no word for all, so `everything` (`forget_permit.py`) reads no forget of everything
there. The call text names the locker, and the card lists it. Over the 3,120 mixed cases of the
third audit of 2026-11-26 these are 4 of the 26 rows asked to keep still deleted
([readings](../../readings/forget-form-cells.md#mixed-messages-of-the-third-audit-2026-11-26)).

## What to do

1. Write the two messages above as tests first, with the call texts `dulap` and `4242`: the locker
   stays.
2. Find which reader lists the locker, and keep a row a word after `în afară de` names with the
   article `ul`, reader by reader as task 1282 says. Replay over the generator and the word pairs:
   no row newly listed, and count the rows asked to delete newly kept.

## History

- 2026-11-26: filed from the mixed messages of the third audit.
