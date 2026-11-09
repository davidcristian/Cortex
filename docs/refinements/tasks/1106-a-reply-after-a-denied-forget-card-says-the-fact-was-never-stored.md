# A reply after a denied forget card says the fact was never stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

After the person presses Deny on a `forget_memories` card, the result is `USER_DECLINED_MSG`,
which tells the model to say the action was not done because it was declined. One live draw on
the `cortexn17` stack, 2026-11-09, after two chats stored `Merke dir bitte: Meine Postleitzahl
ist 7319.` and `Merke dir bitte: Mein Türcode ist 7319.`: `Vergiss meinen Türcode, aber behalte
die Postleitzahl.` drew a call with the text `Türcode`, the card listed the door row, the card
was denied, and the reply said `Ich habe keinen "Türcode" in meinen Erinnerungen gespeichert,
daher musste ich nichts löschen.` with no closing note. Both rows remain, so the reply states
what the store does not hold, and the person may not ask again.

## What to do

1. Draw the flow above and its English form a few times on both builds with a rule written
   first, counting replies that call a denied fact not stored.
2. Try a note the brain appends after a denied forget card, saying the listed exchanges are
   still remembered, before any wording change to `USER_DECLINED_MSG`.

## History

- 2026-11-09: filed from a live confirmation turn in the third audit of the night (`live.sh`,
  `live.log` and `live.jsonl` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`).
