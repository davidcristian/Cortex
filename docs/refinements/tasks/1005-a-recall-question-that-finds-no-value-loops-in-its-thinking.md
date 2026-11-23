# A recall question that finds no value loops in its thinking

**Status:** declined 2026-11-23
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

On 2026-11-07 the cortex was asked `Reply with only the number: which number did I ask you to
keep?` with a gym locker code stored. Recall returned an older memory about a car, and the
thinking repeated `Wait, I'll try "None".` and `Actually, I'll just say "None".` for about 6,000
words until the length limit, 166 s into the turn, so the reply was only the capped note
([readings](../../readings/forget-value-repeats.md#baseline-draws-2026-11-07)). In two more draws
of the same message the reply was `0`, an invented value, and that exchange was stored.

## What to do

1. Draw the message five times with the code stored, and count the turns whose thinking repeats
   one line until the limit and the replies that state a number not stored.
2. Check whether the repeated line check of
   [ADR-0048](../../adr/ADR-0048-generation-bounds.md) decision 17 reads the thinking as well as
   the reply, and if not, compare a stop on repeated thinking lines against the length limit.

## History

- 2026-11-07: filed from the baseline draws of the value repeats record.
- 2026-11-23: declined. Five draws of the message with the code stored, on the cortex of today's
  compose defaults, read 0 of 5 traces repeating a line to the length limit (longest 12,888
  characters, no line twice in a row) and 0 of 5 replies stating a number not stored; all five
  said no number was asked for. The repeated line check reads reply text only, and with no loop
  there is no row to weigh a stop on trace lines against
  ([readings](../../readings/single-draw-recounts.md#a-recall-question-that-finds-no-value)).
  The judge passed over the code note in all five, which is filed as
  [task 1312](1312-a-question-for-the-number-to-keep-recalls-the-car-note-and-not-the-code.md).
