# A short compound stem names every word it starts

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_started` in `forget_unnamed.py` lets the stem of a compound code word in the message name each
row word the stem starts, so that `Fahrradcode` names `Fahrradschloss`. A short English stem
starts unrelated words too. Unit calls of `unnamed` on 2026-11-09, every row holding 7319:
`Forget my passcode 7319, keep everything else.` lists the row `my passport number ends in
7319`, `Forget the carcode 7319, keep everything else.` lists `my card PIN is 7319`, and
`Forget the doorcode 7319, keep everything else.` lists `the doorbell battery model is 7319`.
An approved card then deletes a row the person asked to keep, the card's unsafe direction.

## What to do

1. Write the three messages above as tests first, beside near misses that must still name the
   row: `Fahrradcode` for `Fahrradschloss` and `Türcode` for `Haustür` is not one.
2. Decide which continuations a stem may have (a German compound joint, a plural), then replay
   every recorded forget string through the old and new reader.

## History

- 2026-11-09: filed from unit calls in the third audit of the night (`probe6.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`).
