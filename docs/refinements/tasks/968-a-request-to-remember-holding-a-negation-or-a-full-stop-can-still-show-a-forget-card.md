# A request to remember holding a negation or a full stop can still show a forget card

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`unasked_forget` (`unasked_tools.py`) leaves the tool callable on a request to remember holding a word
that can retract something, a negation, a question or a second sentence, so that no forget request is
refused ([readings](../../readings/forget-refused-on-remember.md#what-is-refused)). So `Remember that I don't eat pork.` and `Please remember
this: my landlord is called Mr. Weber.` can still call `forget_memories` with the fact, and an approved
card on a stored row deletes it. 27 of the 129 recorded messages that ask to remember keep the tool.

`_WISH` keeps the tool too, on purpose for `I want` and `I need`, and by accident for a longer word it
starts: `my bank's name is Askari` (`ask\w*`), `sewing needles`, `my favourite saying`, `a bank teller`.
[12 draws](../../readings/forget-refused-stated-fact.md#facts-holding-a-wish-word-2026-10-31) with the
fact stored showed no call and no card, too few to clear the rate.

## What to do

1. Draw how often such a message calls the tool with a stored row, with facts holding "not", "no",
   "old", a wish word and a title with a full stop.
2. Only on those rows, narrow the reader with near-miss tests first. Every wording of a request to
   forget must keep the tool.

## History

- 2026-10-31: filed from the check of refusing a forget call.
