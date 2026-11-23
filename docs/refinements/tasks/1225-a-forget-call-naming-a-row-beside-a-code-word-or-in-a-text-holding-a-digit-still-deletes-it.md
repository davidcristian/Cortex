# A forget call naming a row beside a code word or in a text holding a digit still deletes it

**Status:** done 2026-11-21
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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
- 2026-11-21: done. Both forms still deleted the row before the change. `message_rows`
  (`forget_permit.py`) now narrows both. In a message holding no digit whose part asking to
  forget names a stored row, a call text holding a digit lists only the rows so named and each
  row holding a whole value of one, as a recall does (`_same_fact`). In a message whose part
  asking to forget names no stored row and holds no word for all, a call text holding no digit
  lists only the rows whose request holds a code word of that part, when a stored row or a row
  the turn deleted holds one (`_coded`). This is narrower than step 2: the code word names the
  rows holding that same word. Replayed before and after over the 42,356 generated messages,
  1,500 added cases and 6,093 calls of the strings of the brain's forget tests: 0 generated
  cases list a row asked to keep, before and after, no generated or added case changed, no row
  was newly listed, and 605 rows were newly kept in 310 calls of 152 test strings, each a card
  or phone row for the call text `card` or `phone` under a string holding a code word and
  naming neither. One cost is outside the replay: with a code row stored, `Forget that code.`
  with the call text `card` keeps a card the chat just stored, and with the card's value as the
  call text still deletes it. The listing is `cmp_v2.txt` in
  `~/.cache/cortex-run/2026-11-21/f3/`. The forms left are filed:
  [R-1286](1286-a-forget-naming-a-code-deletes-another-row-after-a-word-for-all-or-for-a-code-word-in-another-number.md).
