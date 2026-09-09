# The judged rate and the hand column are compared on a probe and no sweep

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Verified:** 2026-09-09

Opened 2026-09-04 by the close of
[R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), which moved the delivered
judging out of a scratchpad and into `scripts/envelopejudges.py`.

The rates in this ADR's tables were judged by hand, once per sweep, and the replies they were
judged from were not kept. So the machine judge cannot be replayed against them: it was written
from the addenda's descriptions of what the hand judging did, number recall against the body at a
half threshold and a regex over the body's own reporting period, and not from the scratchpad, which
does not exist any more. Where the two columns have been compared is one 72-run probe of the
default pick on 2026-09-04, which the judged-delivery addendum publishes in full: 72 of 72
agreement between the machine column and this agent's own reading of the same 72 replies. It is
two runs, 48 of the three swept shapes over four bodies at two draws and 24 of the summarization
shape at three draws, the second of which is where the bare arm's narrations are.

**What is wrong with the present shape.** A 72-run probe on one pick over two arms and three shapes
is a demonstration that the two columns can agree, not a measurement of how often they do. The
tabled rates span five picks at 288 runs each, and the cells where a proxy is most likely to part
from a reader are the ones the tables call interesting: the extraction cells that produce a bare
comma-joined list, the summarization cells whose failures are narrations of different lengths, and
every cap refusal, where the strict column throws away text the charitable one reads. The probe
reaches the first two of those three on the default pick, one comma-joined list that changes verdict
with the comma reading and twenty four summarization replies read in full, six of them narrations
the floor counted as answers, and it reaches the third on nothing: its one cap refusal came back
empty, which is the case the strict and charitable columns agree on.

**What would close it.** One full sweep of one pick, 288 runs, published with both columns: the
machine rate from `just envelope-floor` and a hand reading of the same replies, cell by cell, with
every disagreement named. The pick to run it on is the one whose failures are quiet, since a
narration is what the recall proxy has to separate: `Qwen3.5-0.8B`, whose constrained extraction
cell at 12 of 32 is the worst in the arc and therefore the cell where a proxy that ranks rather
than separates would show. The roster alternate is a different entry, `Qwen3.5-2B`, and its own
constrained extraction cell reads 23 of 32. If the two columns disagree anywhere, the
disagreement decides whether the tabled rows keep their meaning under a machine judge or whether
the record needs a second column of its own.

## Trail

- 2026-09-04: opened by the close of
  [R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), whose live run compared the
  two columns on 48 replies of the default pick and found them identical, which is a probe and not
  a sweep.
- 2026-09-09: claims held to the record, and two were wrong on the day this was written. The probe
  is 72 runs and not 48: the judged-delivery addendum landed in the same commit as this entry and
  publishes two runs, the 48 this described and a second of 24 summarization draws whose bare arm
  delivered 6 of 12, all of them hand read, agreeing 72 of 72. And the pick this entry proposes
  was named twice over: the roster alternate is `Qwen3.5-2B`, while the 12 of 32 extraction cell
  belongs to `Qwen3.5-0.8B`, which is the pick the argument wants. What stands is the subject: five
  picks at 288 runs each are tabled and no pick has a sweep with both columns.
