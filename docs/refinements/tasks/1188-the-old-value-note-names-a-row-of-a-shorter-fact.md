# The old value note names a row of a shorter fact

**Status:** done 2026-11-14
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`_replaced` (`memory_old_value.py`) takes a row whose fact words are all among the statement's
own, so `My new number is 0721 555 019.` names the row `my number is 0721 555 018`
([the reader](../../readings/forget-refused-statement-old-row.md)). The same test names a row of
another fact that a qualifier word separates: `My work phone is 0721 555 019.` and `My sister's
phone is 0721 555 019.` beside `my phone is 0744 111 222`, and `My gym code is 4242.` beside `my
code is 1234`. The note then calls the person's own phone or code the value the message corrects
and offers to forget it. A word marking the stated value as past is the worst case: `My old phone
number was 0744 111 222.` beside `my phone number is 0721 555 019` (and `My previous address was
12 Elm Street.`, `My old locker code was 1234.`) names the current value as the one the message
corrects. Since the possessive and digit checks the reader also gives no note where the tree
before them did: values with no digit (`My wifi password is sunflower.` beside `daisy`, `My blood
type is A+.` beside `O-`, a name or an email address), a new value with no digit beside an old one
with a digit (`sunflower` beside `hunter22`), and another possessive for a shared fact (`Our wifi
password is 5528.` beside `my wifi password is 1234`).

## What to do

1. Write tests first: the work phone, sister's phone, gym code and `old` or `previous` statements
   above give no note; `My new number`, `My current number` and `My alarm code is now 5528.`
   still name the old value.
2. Take a row only when its fact words equal the statement's less the words that state a change
   (`new`, `current`, `actual`, `now`), written as a set the tests list.
3. Replay every recorded message and test string through `hold_old_value`, and decide whether a
   capitalized or email value can count, with a row set holding names.

## History

- 2026-11-13: filed by the second audit of the night, which made the reader compare the possessive
  and require a digit in both values.
- 2026-11-14: done. `_replaced` takes a row only when the message's fact words are the row's plus
  at most `new`, `current` or `actual` (`now` after the fact words reaches no row through the
  search), and `FACT_VALUE` reads only `is` and `are`, so a past value on either side names
  nothing. A replay of 188,929 strings named no new row and lost 903 notes; 39 of them are the
  cost, `My phone number` beside `my number`. A value with no digit and another possessive still
  name nothing, since `My sister is Maria.` beside `my sister is Ana` names a second sister
  ([readings](../../readings/forget-refused-statement-old-row.md#equal-fact-words-and-the-present-tense-2026-11-14)).
