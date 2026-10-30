# A request to remember can call the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

A request to remember a fact makes the cortex call `forget_memories` with the fact as the text in
about one draw in five. The call matches nothing and shows no card, but it marks the turn
(`TaintLedger.forget_asked`), so `memory_withheld` stores nothing and the reply ends with the
unkept note: the person has to send the fact again. On 2026-10-30, R01 to R14 of
[forget-card-on-remember.md](../../readings/forget-card-on-remember.md#more-forget-calls-with-schedules-on-the-separation-2026-10-30)
called it in 10 of 28 draws with schedules on, 7 of 28 in a second run and 9 of 56 with
schedules off; RC called it in 9 of 55 on 2026-10-29. Plain statements of a value ("My locker code is 7319.") called it in 4 of 6
([readings](../../readings/forget-request-wordings.md#thirteen-more-wordings-the-draws-2026-10-30)).

The mark cannot simply be dropped for a forget that matched nothing: a forget request naming a
value that was never stored ("Forget that my passport number is X4821937.") also matches nothing,
and its turn must not store the value. Telling the two apart reads the message, which is the query
check of [R-923](923-a-forget-request-with-no-call-is-recorded.md).

## What to do

1. Write rows and a rule into the readings before any baseline. Done on 2026-10-30
   ([readings](../../readings/forget-card-on-remember.md#a-forget-that-matched-nothing-on-a-request-to-remember-rows-and-rule-2026-10-30)),
   with its baseline: R01 to R14 failed in exactly the 7 of 28 draws that called the tool, and
   W01, W06 and P01 passed in every draw.
2. Build the candidate and draw it against that rule. It needs two typed inputs. The forget tool
   must report a run that matched nothing apart from one that deleted rows, since `ToolRun` keeps
   only a name and `ok`, and both are `ok`. And the message must be read as a request to remember
   ("remember", "note that", "keep in mind", "don't forget") beside `asks_not_kept`
   (`memory_request.py`), so that a message in another language, which neither reads, still
   withholds the turn. A sentence in the tool's description is not a candidate: it failed its
   rule on 2026-10-29
   ([readings](../../readings/forget-card-on-remember.md#the-forget-of-a-text-on-a-request-to-remember-the-draws-2026-10-29)).

## History

- 2026-10-30: filed from the separation of the forget calls on requests to remember, which ended
  without naming the schedule tools as the cause (R-923).
- 2026-10-30: the premise holds, and the no-call check that shipped for R-923 does not change it,
  since `asks_not_kept` reads none of R01 to R14. Step 1's rows and rule were written before any
  draw and the baseline drawn: R01 to R14 failed in exactly the 7 of 28 draws that called the
  tool, the null result the rule names. Left open for the candidate.
