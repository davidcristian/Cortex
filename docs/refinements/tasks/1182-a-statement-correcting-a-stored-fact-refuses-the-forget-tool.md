# A statement correcting a stored fact refuses the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`forget_unrequested` (`forget_unrequested.py`) refuses the forget tool on an English statement of
a fact (`_states_in_english`) that holds no word of `RETRACT_WORDS`. A statement can correct a
stored fact without such a word: `My alarm code is now 5528.`, `My birthday is actually 12 May.`,
`My new number is 0721 555 019.`, `My current number is 0721 555 019.` and
`My phone number was 0721 555 019.` are all refused at HEAD `c0e02329e` (and at the start build
`cec7c748f`, which refused every message with no such word). The older row then stays, and the
old value note (`memory_old_value.py`) does not appear, since it reads only a message that names
the old value (`, not 4826`, `instead of`). Refusing keeps the new fact stored, and a word list
widened to read these regressed on earlier nights.

## What to do

1. Write tests first: each statement above, beside a stored row holding the same fact with another
   value, ends in a reply that says the older row is still in memory.
2. Prefer a brain-appended note over a wider reader: when a refused statement names a fact that a
   stored row holds with another value, append a note naming that row, as the old value note does.
3. Replay every recorded message and test string, and draw the store turn of
   `My alarm code is now 5528.` beside a stored `My alarm code is 4826.`.

## History

- 2026-11-13: filed by the first audit of the night.
