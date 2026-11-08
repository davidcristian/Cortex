# A Romanian reminder reply holds a broken word

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-11-08

One live turn of `Amintește-mi la ora 18 să scot gunoiul pentru colectarea de luni.` on the stack
cortex (gemma-4-12B, text only) replied `Am programat unKy memore pentru astăzi, la ora 18:00`,
where a Romanian word for a reminder (`un memento`) is broken. The schedule call and the item were
right. One draw is not a rate.

## What to do

1. Draw the message 8 times in new chats, with a rule written first, and count replies holding a
   word that is not Romanian. Compare the same count for two other Romanian reminder messages.
2. If the form repeats, read the sampling settings the cortex runs with before any prompt change.

## History

- 2026-11-08: filed from a live draw recorded in
  [the readings](../../readings/schedule-weekday-day-after.md#the-refusal-or-a-note-2026-11-08).
