# A round can repeat an earlier sentence in other words

**Status:** done 2026-11-05
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`OpeningHold` (`round_opening.py`) drops an opening sentence only when an earlier round streamed it
word for word. In 6 of the 20 A4 draws of
[reply-repeat-across-a-tool-call.md](../../readings/reply-repeat-across-a-tool-call.md#more-than-one-repeated-sentence-result-2026-10-31),
the second round opens with the first round's first sentence, which is dropped, and goes on with its
second sentence in other words: `I have also removed the phone number 0612345678 from my memory.`
against `I have also removed the phone number 0612345678 from my memory as you requested.`. The
reply says the same thing twice.

## What to do

1. Write a rule for when a sentence counts as the same one, and test it first on the recorded rounds
   of that readings record's run log, which hold the 6 sentences. A sentence that adds a fact stays,
   so its near misses are tests before any code: the same opening with a new ending, and a number or
   name that differs.
2. If no rule keeps those near misses, decline the task with the counts; the reworded sentence is
   then what the reply shows, and it says nothing false that the first round did not.

## History

- 2026-10-31: filed when the hold began dropping every opening sentence repeated word for word.
- 2026-11-05: done for the recorded form. The run log holding the 6 sentences was lost with a
  reboot, and the readings quote one: it differs from the first round's sentence only by a closing
  `as you requested`. `OpeningHold` now reads a sentence with a closing `as you asked` or `as
  requested` and one without it as the same. Its tests keep the near misses: a changed number or
  ending, an added fact, a question, and a different closing `as`. Redrawing the rows for the other
  5 forms is
  [R-979](979-the-other-rewordings-of-a-repeated-sentence-are-not-recorded.md).
