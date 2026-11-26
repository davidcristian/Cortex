# A forget of a row named Don beside a negated keep clause keeps that row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`parts` (`forget_clauses.py`) moves the word just before a negation of one letter, as `don` of
`don't`, into the keep clause it opens. Neither `_split` (`forget_unnamed.py`) nor `held`
(`forget_inside.py`) reads a fact in that word, so `Forget Don, don't remove the card.` deletes
the row of a person called Don for the call texts `4242`, `Don` and `phone`
([readings](../../readings/forget-keep-any-reading.md#a-contracted-negation-2026-11-26)). Drawn
with the rows seeded, that message deleted Don's row alone in all 8 draws
([readings](../../readings/forget-readers-live-draw.md#one-form-per-change)).

`Forget Don's phone 4242, don't delete the card.` and `Forget the phone of Don, don't forget the
card.` delete the person's own phone row, which neither names: over the 16 cases naming Don's
phone in `don.json`, that row is listed in 3 of the 8 where the message does not ask about it,
at the tree before the `don` rule and after it. The word `phone` names every row whose request
holds it, and no reader reads the owner a word such as `Don's` or `of Don` names. The word pair
sets hold no row of a named person and no possessive, so they count none.

## What to do

1. Draw the other `Don` forms of `don.json` live with the rows seeded, as `Forget everything,
   don't forget Don.` and `Forget the card, don't forget the phone.`: no row the message keeps is
   deleted.
2. Design a reader of the owner a row word names, as `Don's phone` against `my phone`, that only
   narrows the rows a row word names. Count it over the `Don` cases and a family of owners in five
   languages, then build it when no row asked to keep is newly listed.

## History

- 2026-11-26: filed from the audit replay of the `don` rule, with the cases in `gen.py` and
  `don.json` in `~/.cache/cortex-run/2026-11-26/a1/`.
- 2026-11-26: `held` reads no word `contracted` marks; the owner reader of `Don's phone` is not
  a plain shape and stays open, with its count above.
- 2026-11-26: `Forget Don, don't remove the card.` drawn with the card, the phone and Don's row
  seeded, 8 draws, every card approved: Don's row deleted in all 8 (calls `Don` and `Don's
  phone`), the card and the phone kept. The other forms are left to a later run.
