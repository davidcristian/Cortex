# A call text that is the row word a later clause keeps lists that row

**Status:** done 2026-11-25
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over a locker code `4242` and a phone `0721 555 4242`, in unit calls through `ForgetChosenTool`,
`Forget my phones 1234, the phone stays.` with the call text `phone` lists
the phone, and so do `Forget my lockers 1234, the locker stays.` and `Forget my remembered
1234, the locker stays.` with the call text `locker`. The same messages with the call text `4242`
keep the row, since a message lacking the call's value reads the end of its forget clause as
the value's place (`forget_end` in `forget_clauses.py`). Here the message holds the call text,
but only inside the later clause, so `after_value`, `beside` and `kept_again` start after the
row word and read only `stays`. These are the 3 rows asked to keep that the 4,104 cases of
[the longer forget word readings](../../readings/forget-longer-word-beside-a-value.md#a-message-lacking-the-value-2026-11-24)
still list.

## What to do

1. Write the three forms as tests first, each beside its form with the call text `4242`.
2. Read a call text that is a word naming a row, held only after the first clause holding a
   forget verb, as `kept_again` reads a later place of such a text: as the row's name, with the
   end of the forget clause as the value's place. Or decline with the count of rows that reading
   keeps that the message asks to delete.
3. Replay the 4,104 and 12,768 cases in `~/.cache/cortex-run/2026-11-24/f5/` at the old and new
   tree: no row asked to keep listed, no row newly listed.

## History

- 2026-11-24: filed from the close of the reading of a later clause in a message lacking the
  call's value, which keeps 911 of the 914 word pair rows asked to keep and leaves these 3.
- 2026-11-25: done. A call text that is a word naming a row, held only after the first clause
  holding a forget verb, is read as the row's name with the end of the forget clause as the
  value's place (`_held` in `forget_clauses.py`). It keeps the 3 rows, lists no row newly over
  the six case sets, and keeps 42 rows asked to delete in 21 literal calls
  ([readings](../../readings/forget-longer-word-beside-a-value.md#a-call-text-only-in-a-later-clause-2026-11-25)).
