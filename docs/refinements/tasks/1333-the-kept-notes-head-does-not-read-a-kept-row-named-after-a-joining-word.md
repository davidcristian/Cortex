# The kept note's head does not read a kept row named after a joining word

**Status:** done 2026-11-25
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`false_sentence` (`forget_kept_sentence.py`) reads only the object of a stated removal, up to a
joining word such as `and`, `from` or `to`, a comma or a quote mark. So `I've removed the locker
code and phone number from my memory.`, with the locker deleted and the phone kept, gets the plain
kept note, which lists the phone as still stored, and the false sentence is not quoted. On the
[draws](../../readings/forget-result-texts.md#a-reply-saying-a-kept-row-was-forgotten-2026-11-24)
this form was 11 of the 24 recorded false delete claims, 3 of the candidate's 8 and 7 of the
base's 15. No row is at risk: the note names every kept row.

What would close it: a reading of a word for and that continues the removal's object only when a
kept or deleted row's word comes right after it, written after near misses such as `I've deleted
your locker code and phone stays.` as tests, and replayed over the recorded replies and the
audit's true sentences in `~/.cache/cortex-run/2026-11-24/a2/` (`truesent.py`) with no true
sentence marked. A form that needs a word list to read is declined with the count it leaves.

## History

- 2026-11-24: filed from the offline replays in `~/.cache/cortex-run/2026-11-24/f9/`
  (`replay.sh`, `recorded-new.jsonl`, `live-new.jsonl`).
- 2026-11-25: done. A word for and continues the object when a row's word follows it, after near
  misses as tests; the recorded false claims marked went from 7 to 13 of 24, with no true sentence
  marked ([readings](../../readings/forget-result-texts.md#a-removal-continued-past-a-word-for-and-2026-11-25)).
  The 3 claims naming the phone after `and the` or `and your` are declined: reading them needs a
  word the `the or my` row lacks, or marks a sentence the audit counts as true.
