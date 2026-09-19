# The envelope judges read no form

**Status:** open, fix when it bites
**Trigger:** a seeded sweep in which runs of the two kinds below, counted by hand beside the machine
column because no reader for them is in the tree, lower a control cell's rate until its whole
interval lies under the floor, or lower a published cell's delivered rate out of the Wilson
interval quoted beside it.
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Verified:** 2026-09-19

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
- 2026-09-13: Re-derived against the sweep drawn tonight, and the trigger has not fired. A reader
  beside the machine column was written for the two kinds: one flags a delivered extraction that
  carries more than three words per number and stands on a single line, the other a delivered
  lookup that names a span the body states in another role. Held first to the sweep this entry
  cites, it reproduces both, the constrained extraction of the network body at draw 3 and the two
  raw clinic lookups at draws 1 and 6. Run over the two picks that ship, across the re-table
  samples and tonight's sentence samples together, it counts none of either kind in 435 delivered
  runs of gemma-4-E4B, the default, and one extraction answered in prose, on the clinic body, in
  403 of Qwen3.5-2B, the roster alternate. The fourth subtask shape declared tonight is judged by
  the same number recall, so it sits inside that blind spot, and its runs are inside those counts
  and carry neither kind. One such run cannot move a cell either way: a published cell is 32 runs,
  whose Wilson interval runs at least three runs either side of its rate, and both picks' control
  arms read 88 of 96 or better where a control is refused only when its whole interval lies under
  the floor. The entry stays open, and the pick its own two runs were drawn on, Qwen3.5-0.8B, is
  neither of the two that ship.
- 2026-09-19: Re-derived, and the trigger has not fired: no envelope sweep has been drawn since
  2026-09-13, whose samples under `measurements/envelope-sentence-2026-09-13/` are the latest, and
  no measurement directory written since holds an envelope row. `scripts/envelope*.py` is
  unchanged since the sentence fix that preceded the bullet above. Two things were wrong. **The trigger could not
  fire as written.** It named a reader beside the machine column, and the reader that bullet
  describes was never committed: `scripts/envelopejudges.py` still reads letters, digits and
  calendar instances only, and neither `scripts/` nor the sample directories hold a reader for the
  two kinds, so a new sweep prints the machine column and nothing else. The trigger now says the
  count is taken by hand. **One such run can move a cell.** A run of either kind is a false pass,
  so counting it lowers a delivered rate and never raises it, and the interval's upper half is out
  of play. By `wilson` in `scripts/envelopefloor.py` over 32 runs, a cell delivering one run leaves
  its interval when that run is taken away, a cell delivering two or three needs two taken away,
  four or five needs three, and every cell from six upward needs four to six, so the bullet
  above's "at least three runs either side" is wrong at both ends. Its conclusion for the two picks
  that ship still holds: their counts are 0 of 435 and 1 of 403, and the lowest cell either pick
  delivers across the re-table and sentence samples is 4 of 32, on the alternate, which needs three
  taken away.
