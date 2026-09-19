# The body handed back passes both rates

**Status:** done 2026-09-11
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

On a full seeded review of `Qwen3.5-0.8B`, 16 of 288 replies were the report body handed back,
verbatim or with a word changed, where a summary or an extraction was asked.
`scripts/envelopesamples.py` counted such a reply as usable, since it is neither empty nor the
question handed back, and `scripts/envelopejudges.py` counted it delivered, since it contains every
number the body states. On that pick's bare variant the copies are 6 of the 12 machine deliveries on
the extraction and 6 of 27 on the summarization, so a cell there could read well above what a reader
would give it.

**What closed it.** `copied` in `scripts/envelopejudges.py` scores a reply against its body over
letters and digits with `difflib`, and nine tenths is a copy, argued at the origin with the two
nearest cases on each side. The new fault is `copy`, read on every declared form and no other, and
`delivered` counts a copy as a non-delivery. The lookup form is not exempt, since a lookup answered
with the body passes the period check, so the rule is right to fire there.

## History

- 2026-09-11: opened by the close of
  [R-540](540-the-judged-rate-and-the-hand-column-are-compared-on-a-probe-and-no-sweep.md), whose
  reader-column review of the smallest pick names the sixteen replies. The session that found them
  had spent its time reading the review, and a threshold written against no example is a guess.
- 2026-09-11: done. Checked against HEAD first: `Turn.lapse` read three faults, nothing compared a
  reply with its `context`, and HEAD's reader reproduced the review's machine column cell for cell.
  The plan to catch every reply the reader named and none it kept had no threshold, since the reader
  kept one at 0.987 of the body and named one at 0.897. On the 0.8B review the new rule reads 17
  replies: 14 of the 16 the reader named and 3 the reader kept, each the body at its own length. Of
  the two it passes, a summary reworded and shortened by a tenth sits under the line by that
  decision, and an extraction answered as a summary is in
  [R-639](639-the-envelope-judges-read-no-form.md).
