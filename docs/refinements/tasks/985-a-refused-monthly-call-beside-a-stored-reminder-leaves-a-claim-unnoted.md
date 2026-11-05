# A refused monthly call beside a stored reminder leaves a claim unnoted

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

`unscheduled_claim` (`schedule_claim.py`) appends its note only when no scheduling call in the
turn succeeded. The `YEARLY_DATE` refusal now refuses each monthly call of a turn on new days, so a
turn with two reminders can store one and have the other refused. If the model then does not
retry and replies that both are set, any one successful run hides the claim, and the person is
not told the second reminder does not exist.

Reproduction (`brain/.venv/bin/python`, slot 12 of the 2026-11-05 run): for "Remind me of Anna's
birthday on 11 May and of Tom's birthday on 3 June.", `monthly_for_yearly` refuses a call with
`on_month_days` [2], and `unscheduled_claim` returns false for the reply "I've set both
reminders: Anna's birthday on 11 May and Tom's on 3 June." beside one successful
`schedule_task` run. Whether the model writes such a reply after a refusal is not measured.

## What to do

1. Write rows and a rule into the readings first: two-date requests where one call is refused,
   scored by whether the reply claims a reminder no call stored.
2. If the claim occurs, try a note the brain appends when a `YEARLY_DATE` refusal was never
   followed by a stored call for the same request, kept in the taint ledger and the handoff
   record like `monthly_stored`.

## History

- 2026-11-05: filed from the second audit of the yearly date refusal.
