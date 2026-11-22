# A forget call naming a number the message writes with a letter or as a year keeps its row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-22

`_apart` (`forget_permit.py`) compares the whole values of the call text with those of the
message (`whole_values` in `memory_values.py`). Two messages write a number the call text names
and still share no whole value with it, so the call lists only what the message's own readers
permit, in replayed calls through `ForgetChosenTool` on 2026-11-22:

- `Forget my bike lock code and all 7319s.` with the call text `7319` keeps the locker code
  `7319`, which it deleted before. The message's whole value is `7319s`.
- `Forget the code 1987.` with the call text `1987` keeps a code row whose request holds no
  word `code` (`codul`, `código`), which it deleted before. Neither text holds a whole value,
  because `1987` is read as a year, and `_coded` lists only rows holding the message's word.

Both are kept rows, so the person can ask again with the number alone. Over the strings of the
brain's forget tests they are 7 rows in 2 strings
([readings](../../readings/forget-everything-but-call.md#a-call-naming-a-row-the-message-does-not-name-2026-11-15)).

## What to do

1. Write both messages as tests first, and beside them the calls that must stay kept:
   `Forget my locker code 4242.` with the call texts `my card is 4111` and
   `phone is 0721 555 4242`.
2. Read a call text's number as written in the message when it is the digits of a whole value
   holding one run of digits, or a run of digits outside every whole value. A group of a longer
   value must stay apart, so the second call text above still keeps the phone.
3. Replay the generator and every string of the brain's forget tests: no row newly listed.

## History

- 2026-11-22: filed with the replay of a call text holding a digit beside a message holding
  another value
  ([R-1288](1288-a-forget-message-holding-a-value-deletes-another-row-for-a-call-text-holding-another-value.md)).
