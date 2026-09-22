# The judged rate and the hand-read column are compared on one probe and no full run

**Status:** done 2026-09-11
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

The rates in this ADR's tables were judged by hand, once per measurement, and the replies they were
judged from were not kept, so the machine judge in `scripts/envelopejudges.py` cannot be replayed
against them: it was written from the measurements' descriptions of what the hand judging did,
number recall against the body at a half threshold and a regular expression over the body's own
reporting period. The two columns have been compared on one 72-run probe of the default pick on
2026-09-04, published in full: 72 of 72 agreement between the machine column and this agent's
reading of the same replies. That probe is two runs, 48 of the three subtask shapes over four bodies
at two draws and 24 of the summarization shape at three draws.

A 72-run probe on one pick over two conditions and three shapes shows that the two columns can
agree, not how often they do. The tabled rates span five picks at 288 runs each, and the cells where
a machine judge is likeliest to differ from a reader are the extraction cells that produce a bare
comma-joined list, the summarization cells whose failures are narrations of different lengths, and
every cap refusal, where the strict column throws away text the charitable one reads. The probe
reaches the first two on the default pick and the third on nothing, since its one cap refusal came
back empty, the case both columns agree on.

Closing it means one full 288-run measurement of one pick published with both columns: the machine
rate from `just envelope-floor` and a hand reading of the same replies, cell by cell, with every
disagreement named. The pick to run it on is `Qwen3.5-0.8B`, whose constrained extraction cell at 12
of 32 is the worst measured and therefore the cell where a judge that ranks rather than separates
would show.

## History

- 2026-09-04: opened by the close of
  [R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), whose live run compared the
  two columns on 48 replies of the default pick and found them identical.
- 2026-09-09: two claims were wrong on the day this was written. The probe is 72 runs and not 48,
  since the judged-delivery change was committed with this entry and publishes a second run of 24
  summarization draws. And the pick was named twice over: the roster alternate is `Qwen3.5-2B`,
  while the 12 of 32 extraction cell belongs to `Qwen3.5-0.8B`, which is the pick the argument
  wants. The subject stands: five picks at 288 runs each are tabled and none has both columns.
- 2026-09-11: done. One full seeded 288-run measurement of `Qwen3.5-0.8B` on the current image, read
  whole by a person beside `just envelope-floor`: the two columns agree on 250 of 288, and the 38
  that differ are of three kinds, each named run by run in the reader-column record. The tabled rows
  keep their meaning under the machine judge, which reproduces the hand rule the tables were written
  under. What neither rule sees is the body handed back, 16 runs, filed as
  [R-634](634-the-body-handed-back-passes-both-rates.md), and a lookup reply that quotes the body's
  phrase beside an invented month, 16 runs, filed as
  [R-635](635-the-lookup-judge-passes-an-invented-instance-beside-the-bodys-phrase.md). The
  remaining six are right answers the strict naming column fails, which the tool already has a
  column for. Two cells moved on the new build and the tabled row stays, being a dated reading on
  the older digest.
