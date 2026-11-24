# The kept note does not say how to ask for a row it names

**Status:** declined 2026-11-24
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

The card line `KEPT_LINE` and the reply note `KEPT_NOTE` (`forget_unnamed.py`) name the rows a
forget kept and say the message was not read as meaning them. Neither says what to send to have
one of those rows deleted. Over the rows `Remember that my locker code is 4242.`, `Remember that
my card is 4111 1111 1111 4242.` and `Remember that my phone is 0721 555 4242.`, `Forget the locker
4242 including the phone.` keeps the phone, and `Forget the phone 4242.` then lists and deletes
it, so a message naming only that row and the value is one such form. ADR-0075 states that the
note asks for nothing, and `test_the_kept_note_names_each_row_and_asks_for_no_forget`
(`test_forget_just_said.py`) fails a note holding the word `forget`. The ADR and the rule written
before the draws (`docs/readings/forget-what-was-just-said.md`) state this where they name the
note and give no reason there, so a sentence saying how to ask needs that reason found first.

## What to do

1. Find why the note may hold no forget verb: check whether a reader of an earlier reply, such
   as the one that keeps the forget tool after a reply naming a forget, reads a note the brain
   appended. Write the reason into ADR-0075.
2. If no reader reads the note, write a second sentence in the five note languages saying to
   ask again naming only that row, true on every turn the note reaches, with a test that the
   form it names deletes the row for each reason a row is kept.
3. If a reader does, decline with that reason.

## History

- 2026-11-15: filed with the change that gives the card line and the reply note a reason true
  for every kept row ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-24: declined. No reader of an earlier reply reads a statement in the note:
  `_asks_about_forgetting` (`unasked_tools.py`) reads the whole last reply but only a question,
  and `_exchange` (`tool_loop.py`) reads it through `model_text`, which drops the note. The reason
  is the rows the note names: they include a row a keep clause of the message names, as the card
  of `Forget all 4242, card stays.` and `Forget all 4242 except the card.` for the call text
  `card`, so a sentence on how to delete a named row would say how to delete a row the person
  asked to keep. ADR-0075 now gives that reason where it says the note asks for nothing.
