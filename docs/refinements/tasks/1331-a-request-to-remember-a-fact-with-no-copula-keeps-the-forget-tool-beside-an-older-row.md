# A request to remember a fact with no copula keeps the forget tool beside an older row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`forget_unrequested` (`forget_unrequested.py`) keeps the forget tool on a request to remember in
French, German, Spanish or Romanian whose fact holds no copula, such as `Merk dir, dass mein Hund
Bello heißt.`, `Recuerda que tienes cita a las 9.` and `Ține minte că sora mea vine mâine.`
([task 1197](1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)).
Into an empty store the cortex called the tool unasked in 11 of 24 draws of these three forms,
each call named the new fact, and no row was lost
([readings](../../readings/forget-refusal-stated-fact.md#the-store-turn-of-four-forms-the-rule-keeps)).
With an older row stored that holds the same words, such a call can match it and its approved
card deletes it. With an older row of the same fact stored, 16 draws per form, the cortex
deleted the old row unasked in 3 of 48 draws (1 of 16 for the Bello form, 0 for the cita form, 2
for the sora form), and each time the person ended up with neither value
([readings](../../readings/forget-refusal-stated-fact.md#three-forms-with-no-copula-and-an-older-row-stored-2026-11-25)).

## What to do

Reading these forms as stated facts costs more than it prevents: of two shapes counted before any
build, each newly refuses more than half of a family of requests to forget phrased as a request to
remember, such as `Merk dir, dass meine Karte 4242 weg muss.`
([readings](../../readings/forget-refusal-possessive-subject.md)). So the next remedy reads the
forget call, not the message's form.

1. Write the rule first, then build a check on the call: on a turn whose message `asks_kept_other`
   reads as a request to remember, refuse a forget call whose text holds a word the message does
   not hold. In each of the six draws that deleted an old row unasked, a call named such a word
   (`Rex`, `vineri`, `rouge`, `carnívoro`), and every other call of the 2026-11-25 draws named only
   words of the message, except one, which matched no row
   ([readings](../../readings/forget-refusal-possessive-subject.md#what-the-losing-calls-named)).
   Write the near misses as tests first: a call naming the stored value of a row the message asks
   to drop (`4111 1111 1111 4242` for `Merk dir, dass meine Karte weg muss.`), and a call that
   changes only the case of a word (`Mein Hund heißt Bello.`).
2. Before the build, count its cost over the forget generator and both families of the readings,
   with the calls the card generator uses, as rows asked to delete that are now kept, and replay
   it over the strings of the readings.
3. Draw the Bello and sora forms live on the new check with the seeds of the readings, 16 draws
   each, every card approved: no old row may be deleted.

## History

- 2026-11-24: filed when
  [task 1197](1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)
  was declined on draws into an empty store.
- 2026-11-25: step 1 drawn with an older row stored, two stack runs of 8 draws per form: 3 of
  48 draws deleted the old row unasked and lost both values, so step 2 opens. Steps 2 to 4 now
  name the shape, the cost count and the live draw. Left open, since the shape, its count and
  its draw did not fit the slot together.
- 2026-11-25: the stated fact shape and its cost were counted before any build, and no reader was
  built. A possessive subject and two to five words newly refuses 147 of 239 and 150 of 238
  requests to forget in two families; the same shape with a name or a number, 10 of 239 and 150
  of 238. The rule allowed at most half of each. Steps now name a check on the call text. Left open.
