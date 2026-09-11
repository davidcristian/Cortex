# The envelope judges read no form

**Status:** open, fix when it bites
**Trigger:** a seeded sweep in which runs of the two kinds below, counted by a reader beside the
machine column, move a control cell across the floor or move a published cell's delivered rate
outside the Wilson interval quoted beside it.
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-09-11 by the lapse addendum at the origin, which closed the two lapses the sweep-columns
addendum found. The rules `scripts/envelopejudges.py` now holds read a reply's letters, digits and
calendar instances, and two kinds of wrong answer carry nothing those rules read.

**An extraction answered in prose.** The recall judge counts the body's numbers in the reply, so a
summary that carries them passes an extraction. On the full seeded sweep of `Qwen3.5-0.8B` that is
one run of 96, the constrained extraction of the network body at draw 3, which scores 0.736 against
its body and is not a copy.

**A lookup that answers with a span the body states in another role.** The clinic body says two
clinicians were on leave `for the second half of the month`, and two raw lookup replies, draws 1
and 6, answer that the report covers the second half of the month. The span is the body's own, so
the invented-instance rule has nothing to refuse, and what is wrong is the role the reply gives it.

Both need a reading of the reply's shape or syntax rather than its tokens: whether an extraction is
a list, and which span a sentence says the report covers. The judged-delivery addendum at the origin
rejected a second completion as the judge, and the instruction addendum's fifth decision says why a
detector over prose is not structural, so neither is built on one pick's three runs. A bare
summarization reworded and shortened by a tenth, which the reader of that sweep named a copy once
and kept three times, sits under the copy line by the lapse addendum's decision and is not this
entry.

## Trail

- 2026-09-11: opened by the close of
  [R-634](634-the-body-handed-back-passes-both-rates.md) and
  [R-635](635-the-lookup-judge-passes-an-invented-instance-beside-the-bodys-phrase.md), whose
  lapse addendum names the three runs.
