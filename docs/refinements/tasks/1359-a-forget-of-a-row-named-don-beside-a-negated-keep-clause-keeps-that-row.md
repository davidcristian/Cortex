# A forget of a row named Don beside a negated keep clause keeps that row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`parts` (`forget_clauses.py`) moves the word just before a negation of one letter, as `don` of
`don't`, into the keep clause it opens. `_split` (`forget_unnamed.py`) reads no fact in that word,
but `held` in `forget_inside.py` reads every word of the keep clause, so a row whose request names
a person called Don is read as kept. Over 44 messages naming Don beside `don't`, 57 of 64 rows
asked to delete are kept, against 44 at the tree before the `don` rule: `Forget Don, don't remove
the card.` keeps Don's row for the call texts `4242`, `Don` and `phone`. That is the safe
direction. `Forget Don's phone 4242, don't delete the card.` deletes the person's own phone row,
which it does not name, at both trees, and now keeps Don's.

## What to do

1. Read in `held` none of the words `contracted` (`forget_clauses.py`) marks, as `_split` does. A
   candidate of that one line deletes 10 of the 13 rows again and changes no other `Don` case;
   replay it over every case set in `~/.cache/cortex-run/2026-11-26/a1/` so no row asked to keep
   is newly listed, then draw it live with the rows seeded before building it.
2. Find why `Don's phone` names the person's own phone row, and count that over the pairs.

## History

- 2026-11-26: filed from the audit replay of the `don` rule, with the cases in `gen.py` and
  `don.json` in `~/.cache/cortex-run/2026-11-26/a1/`.
