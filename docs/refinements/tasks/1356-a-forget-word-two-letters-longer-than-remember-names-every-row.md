# A forget word two letters longer than remember names every row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, `Forget what you remembered about my
card.` with the call text `4242` deletes the card and the phone, in unit calls through
`ForgetChosenTool`. `remembered` less two letters is `remember`, a word of every stored request,
so `extends` in `forget_named` (`forget_keep_named.py`) reads it as naming every row and the
card no longer narrows the call to the card. `Forget what you remembering about my card.`
deletes the card alone.

## What to do

1. Write the message above as a test first: it deletes the card alone.
2. Find which reader lists the phone and why the locker stays, then make a word every stored
   request holds name no row by `extends`, replayed over the word pairs and the generator so no
   row is newly listed.

## History

- 2026-11-26: filed from the close of
  [task 1304](1304-a-romanian-plural-row-word-in-a-forget-message-names-no-row.md), where the
  probe of a longer word beside `remember` found it.
