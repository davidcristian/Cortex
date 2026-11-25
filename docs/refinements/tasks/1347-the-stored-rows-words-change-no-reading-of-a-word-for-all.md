# The stored rows' words change no reading of a word for all

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`quantifies` (`forget_unnamed.py`) stops a word for all at a word of the stored rows or of the
message. Given no rows, so reading the message's words only, it reads every one of 61,992 pairs
of a message and its rows the same as given the rows: the forget generator, the forget of
everything family and both sets of mixed messages. No forget test fails either, so the rows' part
of the rule has no case that needs it.

`limited` (`forget_kinds.py`) stops the word for all when a word of `named` starts a word
between it and the value, and `named` holds every word `row_words` reads in the message. So a
row's word can add a stop only when it starts a message word that `row_words` drops: a common
word, a function word of the message's language, a word for all, or one under three letters.
`Forget all delete 4242.` beside a Spanish row holding `del` reads as asking for one row given
the rows and for every row given the message's words only; `Forget all lockers 4242.` and
`Forget every Spindcode 4242.` read the same both ways (`q1347.py` in
`~/.cache/cortex-run/2026-11-25/x1/`). The rows' part reaches only such accidents, so a test of
it would assert one.

## What to do

1. Read the message's words only (`quantifies(query, limit=...)` in place of the rows, at its
   three call sites and in `test_forget_every_kind.py`). It reads more messages as asking for
   every row, so draw it with the seeded draw of task 1345 before it ships.

## History

- 2026-11-25: filed by the audit of the night's forget commits; the script is `surv.py` in
  `~/.cache/cortex-run/2026-11-25/a1/`.
- 2026-11-25: found that the rows' part stops a word for all only through a row word that starts
  a message word `row_words` drops; no test written, since it would assert that accident, and the
  removal left for the seeded draw.
