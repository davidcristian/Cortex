# A call refused as already run is repeated until the round limit

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-11-28

On compose defaults the cortex is offered one tool, `forget_memories`. On 2026-11-28 the stack on
those defaults drew `Rappelle-moi demain à 9 heures d'appeler le dentiste.` and `Remind me tomorrow
at 9 to call the dentist.` eight times each, twice, with memory empty
(`~/.cache/cortex-run/2026-11-28/s11/`). In three turns of each sixteen (French seeds 2 and 4,
English seed 1) the cortex called `forget_memories` with the reminder's words (`dentiste`, `demain
à 9 heures d'appeler le dentiste`, `tomorrow at 9 to call the dentist`). The same call ran twice
and returned `nothing was forgotten` both times, and from the next round on the dispatcher refused
it with `REDUNDANT_MSG` (`dispatch.py`), which says not to repeat the call. The cortex repeated it
in every round until the round limit, so each of those turns ended with the rounds note and no
answer, and the turn was not stored.

Nothing was lost, since memory was empty and the call matched nothing. The cost is a turn with no
answer to a plain request. The forget readers are frozen, so the remedy is not a wider forget
reader.

## What to do

1. Find why an identical call ran a second time before it was refused, from the proxy records of
   that run log, and whether that is the dispatcher's intended count.
2. Write the remedy as a change to the tool loop, not to any reader. One form: after a round whose
   every call was refused as already run, send the next round with no tools offered, so the model
   must answer from what it has. A model-read result text never suggests a destructive next step.
3. Write the rule first, then draw: the two messages above eight times each on plain compose
   defaults, before and after, counting turns that end at the round limit; it passes at 0 of 16
   after, with no change on flows 1 and 7 of
   [the smoke flows](../../readings/plain-defaults-smoke-flows.md).

## History

- 2026-11-28: filed from the reminders off draw.
