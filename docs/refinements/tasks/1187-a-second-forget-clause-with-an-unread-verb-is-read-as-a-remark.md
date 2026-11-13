# A second forget clause with an unread verb is read as a remark

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`asking` (`forget_clauses.py`) drops each clause holding no forget verb of `FORGET`, no keep
clause and not the call's value, and `_read` (`forget_inside.py`) then reads row names from the
rest ([the remark reader](../../readings/forget-remark-about-the-value.md)). A clause that asks to
forget a second row with a verb `FORGET` lacks (`wipe`, `drop`, `clear`, `supprime`, `entferne`)
or with no verb (`the card one as well`, `also my phone`, `die Karte auch`) is read as a remark,
so the card keeps that row under its line for a value held only inside a longer one. With the
locker code `4242` and the card `4111 1111 1111 4242`, `Forget my locker code 4242, the card one as
well.` deletes the card at `10a3a5594` and keeps it at HEAD; so do ten other messages, French
and German among them. Keeping is the safe direction of the card, and the card shows the kept row
before the delete; the cost is a second request for a row the person named. `Forget it, the one on
my card.` reads as before, since its asking part names no row.

## What to do

1. Write tests first from the messages above, beside the remark tests of
   `test_forget_side_clause.py`, which must still keep the remark's row.
2. Change the remark's shape rather than the verb list: a remark is a part cut at a relative word
   after the value, or a clause whose subject stands for the value (`it is on my card`, `il est
   noté`, `er steht`); any other clause naming a row is read as asking.
3. Replay every recorded message and test string through the card.

## History

- 2026-11-13: filed by the second audit of the night; the probe is `probe.py` with `cases.json` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot12/`.
