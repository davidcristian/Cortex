# The kept note's head does not read a kept row named after a joining word

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`false_sentence` (`forget_kept_sentence.py`) reads only the object of a stated removal, up to a
joining word such as `and`, `from` or `to`, a comma or a quote mark. So `I've removed the locker
code and phone number from my memory.`, with the locker deleted and the phone kept, gets the plain
kept note, which lists the phone as still stored, and the false sentence is not quoted. On the
[draws](../../readings/forget-result-texts.md#a-reply-saying-a-kept-row-was-forgotten-2026-11-24)
this form was 11 of the 24 recorded false delete claims, 3 of the candidate's 8 and 7 of the
base's 15. No row is at risk: the note names every kept row.

What would close it: a reading of the 6 recorded claims that go on past the list of rows with
`from my memory` or a comma, as `I've removed the locker code and phone number from my memory.`,
that marks none of the true sentences of `truegen.py` (3,711, copied in
`~/.cache/cortex-run/2026-11-25/x3/`) and none of the 17 of `truesent.py` in
`~/.cache/cortex-run/2026-11-24/a2/`, with no word added to a list; or a decline with the 6 when
no such reading exists.

## History

- 2026-11-24: filed from the offline replays in `~/.cache/cortex-run/2026-11-24/f9/`
  (`replay.sh`, `recorded-new.jsonl`, `live-new.jsonl`).
- 2026-11-25: a word for and continues the object when the list runs to the end of the sentence
  and each item after it holds only words naming a row, after near misses as tests. The live draws
  marked went from 7 to 9 of 32, the recorded false claims stay at 7 of 24, and no true sentence
  is marked of 17 or of 3,711
  ([readings](../../readings/forget-result-texts.md#a-removal-continued-past-a-word-for-and-2026-11-25)).
  Reading past the list would mark `I've removed the locker code and card number in memory
  stays.`, which no rule tells from the `from my memory` form without a list of verbs. The 3
  claims naming the phone after `and the` or `and your` are declined: reading them needs a word
  the `the or my` row lacks, or marks a sentence the audit counts as true.
