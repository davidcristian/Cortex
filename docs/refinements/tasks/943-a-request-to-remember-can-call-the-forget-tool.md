# A request to remember can call the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

A request to remember a fact makes the cortex call `forget_memories` with the fact as the text in
about one draw in six. The call matches nothing and shows no card, but it marks the turn
(`TaintLedger.forget_asked`), so `memory_withheld` stores nothing and the reply ends with the
unkept note: the person has to send the fact again. On 2026-10-30, R01 to R14 of
[forget-card-on-remember.md](../../readings/forget-card-on-remember.md#more-forget-calls-with-schedules-on-the-separation-2026-10-30)
called it in 10 of 28 draws with schedules on and 9 of 56 with schedules off; RC called it in 9 of
55 on 2026-10-29. Plain statements of a value ("My locker code is 7319.") called it in 4 of 6
([readings](../../readings/forget-request-wordings.md#thirteen-more-wordings-the-draws-2026-10-30)).

The mark cannot simply be dropped for a forget that matched nothing: a forget request naming a
value that was never stored ("Forget that my passport number is X4821937.") also matches nothing,
and its turn must not store the value. Telling the two apart reads the message, which is the query
check of [R-923](923-a-forget-request-with-no-call-is-recorded.md).

## What to do

1. Write rows and a rule into the readings before any baseline: R01 to R14, a forget request
   naming a value never stored (W01 or `Forget that my passport number is X4821937.`), and P01,
   with what each must store.
2. Weigh the candidates on them: a forget call that matched nothing withholds the turn only when
   the query asks to forget or not to keep (shared with R-923's query check), or a sentence in the
   tool's description saying it never runs on a request to remember.

## History

- 2026-10-30: filed from the separation of the forget calls on requests to remember, which ended
  without naming the schedule tools as the cause (R-923).
