# The old value note names a row of a shorter fact

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`_replaced` (`memory_old_value.py`) takes a row whose fact words are all among the statement's
own, so `My new number is 0721 555 019.` names the row `my number is 0721 555 018`
([the reader](../../readings/forget-refused-statement-old-row.md)). The same test names a row of
another fact that a qualifier word separates: `My work phone is 0721 555 019.` and `My sister's
phone is 0721 555 019.` beside `my phone is 0744 111 222`, and `My gym code is 4242.` beside `my
code is 1234`. The note then calls the person's own phone or code the value the message corrects
and offers to forget it. The same reader gives no note to a correction whose values hold no digit,
such as a name or an email address.

## What to do

1. Write tests first: the three statements above give no note; `My new number`, `My current
   number` and `My alarm code is now 5528.` still name the old value.
2. Take a row only when its fact words equal the statement's less the words that state a change
   (`new`, `current`, `actual`, `now`), written as a set the tests list.
3. Replay every recorded message and test string through `hold_old_value`, and decide whether a
   capitalized or email value can count, with a row set holding names.

## History

- 2026-11-13: filed by the second audit of the night, which made the reader compare the possessive
  and require a digit in both values.
