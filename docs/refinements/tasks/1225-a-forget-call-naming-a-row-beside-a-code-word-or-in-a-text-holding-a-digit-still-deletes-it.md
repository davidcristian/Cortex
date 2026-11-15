# A forget call naming a row beside a code word or in a text holding a digit still deletes it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

The forget card lists a match of a call text holding no digit only when the message permits it,
and only when the message holds a whole value that a stored row holds (`permitted` in
`forget_permit.py`). Two forms outside that rule still delete a row the message does not ask
for, in unit calls through `ForgetChosenTool` over a locker code, a card and a phone that all end
in `4242`:

- `Forget my gym code.` with the call text `phone` deletes the phone. The message holds no value
  and no word of it names a stored row: `gym` is in none, and `code` is a code word, which names
  no fact. `Forget that.` reads the same way and must keep deleting what the call names.
- `Forget my locker code.` with the call text `my card is 4111` deletes the card. The text holds a
  digit, so `permitted` does not read it and `_unnamed_groups` keeps the match only when the row
  holds the text inside a longer value.

The card shows each row before anything is deleted.

## What to do

1. Write the near misses as tests first: `Forget what I just told you.` with the call text `phone`
   must still list the phone, and a recalled exchange holding the value only in its reply must
   still be deleted beside the fact (`test_forget_unnamed.py`).
2. For the first form, read a code word of the message as naming the stored rows whose request
   holds a code word, for a call text holding no digit only: `Forget that code.` with the value of
   a card the chat just stored as the call text deletes the card today and must still.
3. For the second, a row holding a whole value of a permitted row is the same fact (a recalled
   exchange), so permit it; a first build without that kept the recall of
   `test_each_recorded_value_first_draw_still_deletes_every_row`.
4. Replay the pools of the reading: no row newly listed, and each newly kept row one the message
   does not ask for.

## History

- 2026-11-15: filed from the calls the store read of the message's named rows does not reach
  ([readings](../../readings/forget-everything-but-call.md#a-call-naming-a-row-the-message-does-not-name-2026-11-15)).
