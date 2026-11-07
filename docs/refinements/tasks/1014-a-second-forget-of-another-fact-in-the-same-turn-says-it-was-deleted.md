# A second forget of another fact in the same turn says it was deleted

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`ForgetChosenTool._choose` returns `_ALREADY_DELETED` for any call that matches nothing once an
earlier call in the same turn deleted rows, whatever text the later call names. The result tells
the model that the user's request was deleted and not to say it was not stored. When the person
asks to forget two facts and only the first was stored, the second result is false.

Unit reproduction: one row `User: Remember my phone number is 0176 5550 1234.`, then in turn `t1`
a forget of `phone number`, approved (`forgot 1 remembered exchanges`), then a forget of `blue
Fiat`. The second result is `nothing more was forgotten: ... an earlier call in this turn already
deleted what the user asked to forget, so tell the user it was deleted and do not say that it was
not stored or could not be found`, and `matched_nothing` is false, so `forget_unmatched` does not
count it.

## What to do

1. Write the reproduction as a failing test beside `test_forget_after_delete.py`.
2. Return `_ALREADY_DELETED` only when the later text names what an earlier call of the turn
   deleted: a deleted row contained it, or it shares a word or a value with the earlier call's
   text. Otherwise return `_NONE_FOUND`, so the reply says nothing about that fact was stored.

## History

- 2026-11-07: filed by the audit of the forget result that names an earlier delete.
