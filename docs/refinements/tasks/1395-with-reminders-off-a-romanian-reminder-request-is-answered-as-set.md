# With reminders off, a Romanian reminder request is answered as set

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-28

On compose defaults `CORTEX_SCHEDULE_BACKEND` is `none`, so the cortex is offered no scheduling
tool, and nothing in its system message says reminders are off. On 2026-11-28 the stack on those
defaults drew `Amintește-mi mâine la ora 9 să sun la dentist.` three times
([readings](../../readings/plain-defaults-smoke-flows.md#3-and-4-a-reminder-with-reminders-off)).
Each reply said the reminder would fire: `Te voi amintește mâine la ora 9`, `Sigur, am înregistrat
amintirea. Te voi minte mâine la ora 9` and `Voi reține să te reamintesc mâine la ora 9:00`. None
was given the Romanian `UNSCHEDULED_CLAIM_NOTES` note, because `unscheduled_claim` reads a past
tense claim (`am setat`, `am programat`), and these are a promise in the future tense or `am
înregistrat`. The French `Rappelle-moi demain à 9 heures d'appeler le dentiste.` was answered that
no reminder can be set in 2 of 3 draws. In the third, the cortex's thought planned a `set_reminder`
tool it was not offered, it called `forget_memories` twice with the reminder's words (`appeler le
dentiste`, `demain à 9h00`), and it asked for tomorrow's date so that it could set the reminder.
Memory was empty, so nothing matched and the French unmatched note was right.

## What to do

1. Do not widen the claim reader: a future tense promise is one more form, and the next draw finds
   another. A note that is true on every turn it reaches needs no reader of the reply. With no
   schedule store configured, `(Reminders are off here, so no call in this turn can set one.)` is
   true on every turn. Show it, in the message's language, on a turn whose message the reminder
   reader of `unasked_tools.py` (`_REMINDER`) reads; a reply note's safe direction is to show.
   The alternative is a sentence in the system message when no scheduling tool is offered, which
   is a prompt rule and reaches only a cortex that follows it.
2. Write the rule first, then draw. For example: the two messages above and `Remind me tomorrow at
   9 to call the dentist.` eight times each with the backend off, before and after, counting
   replies that promise a reminder with no note; it passes at 0 of 24 after, with the note on no
   turn of A1 and A7 of the readings.
3. The forget calls are a fact for this task, not a forget task: the forget readers are frozen,
   and with rows stored the call shows a card that keeps them unless the person approves.

## History

- 2026-11-28: filed from the plain defaults smoke flows.
