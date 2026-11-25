# A continued removal object marks a true sentence whose next subject is a bare row word

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`false_sentence` (`forget_kept_sentence.py`) continues a removal's object past a word for and when
every naming word up to the next joining word names a row. A true sentence whose second clause
opens with a kept row's word and no determiner then has that subject read as part of the object,
when a joining word or a second word for and comes before its verb. With the locker deleted and the
card and phone kept, `I've removed the locker code and card number in memory stays.` and `I've
deleted the locker code and card number and phone number are kept.` are marked, so the note's head
calls a true sentence wrong. No row is at risk: the note lists every kept row either way.

Over `truegen.py` in `~/.cache/cortex-run/2026-11-25/a3/` (3,711 true sentences from the rows' own
words in five languages, each of the three rows deleted in turn and the other two kept), the reader
marks 1,125: all 900 with a bare kept row word, a joining phrase such as `in memory`, `on file` or
`of yours`, then a verb, and all 225 naming two kept rows joined by a word for and before their
verb. The reader before the continuation marks none of the 3,711. With a determiner, as in `and
your card number in memory stays`, none is marked, and no recorded or live reply has this form.

A narrowing measured offline (`variant_fks.py` in the same directory): keep a continued object
only when it ends at the clause's end or at `from`, and otherwise end it at the first word for and.
It keeps 13 of the 24 recorded false claims and 12 of the 32 live draws marked, and leaves 150 of
the 3,711 marked, each with `from before` ahead of its verb. It adds a one-word list, so it is not
built.

What would close it: one rule under which a bare row word that opens a clause after a word for and
leaves the sentence unmarked in every form of the generator, with its cost stated as the recorded
and live claims it unmarks; or a decline with the 1,125 when no rule reads it without a list of
verbs.

## History

- 2026-11-25: filed from [task 1333](1333-the-kept-notes-head-does-not-read-a-kept-row-named-after-a-joining-word.md),
  from the true sentences of `truegen.py` replayed through the reader before and after the
  continuation.
