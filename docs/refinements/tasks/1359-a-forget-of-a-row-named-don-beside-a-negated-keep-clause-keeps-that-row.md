# A forget of a row named Don beside a negated keep clause keeps that row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`parts` (`forget_clauses.py`) moves the word just before a negation of one letter, as `don` of
`don't`, into the keep clause it opens. Neither `_split` (`forget_unnamed.py`) nor `held`
(`forget_inside.py`) reads a fact in that word, so `Forget Don, don't remove the card.` deletes
the row of a person called Don for the call texts `4242`, `Don` and `phone`
([readings](../../readings/forget-keep-any-reading.md#a-contracted-negation-2026-11-26)). That
reading in `held` has been replayed, not drawn live.

`Forget Don's phone 4242, don't delete the card.` and `Forget the phone of Don, don't forget the
card.` delete the person's own phone row, which neither names: over the 16 cases naming Don's
phone in `don.json`, that row is listed in 3 of the 8 where the message does not ask about it,
at the tree before the `don` rule and after it. The word `phone` names every row whose request
holds it, and no reader reads the owner a word such as `Don's` or `of Don` names. The word pair
sets hold no row of a named person and no possessive, so they count none.

## What to do

1. Draw `held` reading no contracted word live with the rows seeded, `Forget Don, don't remove the
   card.` and the other `Don` forms of `don.json`: Don's row is deleted, the card kept.
2. Design a reader of the owner a row word names, as `Don's phone` against `my phone`, that only
   narrows the rows a row word names. Count it over the `Don` cases and a family of owners in five
   languages, then build it when no row asked to keep is newly listed.

## History

- 2026-11-26: filed from the audit replay of the `don` rule, with the cases in `gen.py` and
  `don.json` in `~/.cache/cortex-run/2026-11-26/a1/`.
- 2026-11-26: `held` reads no word `contracted` marks; the owner reader of `Don's phone` is not
  a plain shape and stays open, with its count above.
