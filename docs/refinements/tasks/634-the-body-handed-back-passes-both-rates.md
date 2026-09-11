# The body handed back passes both rates

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-09-11 by the close of
[R-540](540-the-judged-rate-and-the-hand-column-are-compared-on-a-probe-and-no-sweep.md). On a
full seeded sweep of `Qwen3.5-0.8B`, 16 of 288 replies were the report body handed back, verbatim
or with a word changed, where a summary or an extraction was asked. `scripts/envelopesamples.py`
counts such a run as stood, since it is neither empty nor the ask handed back, and
`scripts/envelopejudges.py` counts it delivered, since it carries every number the body states. On
that pick's bare arm the copies are 6 of the 12 machine deliveries on the extraction and 6 of 27 on
the summarization, so a cell there can read well above what a reader would give it.

**What would close it.** A lapse beside `echo` in `envelopesamples.Turn.lapse`, say `copy`, read
the way `echo` is read: over letters and digits alone, so punctuation and wrapping cannot hide it.
Equality catches the verbatim half; the near-verbatim half, a copy with one word changed or one
clause dropped, needs a containment or a similarity rule with a threshold argued from the sweep's
own replies, and that threshold is the decision this entry defers. The lookup shape is exempt by
construction, its body never being an answer to its question. The stood rate and the delivered
rate both change, so the tabled rows should be re-read under the new lapse before any is quoted
beside it.

**Why it was left.** The sitting that found it had spent its runway on reading the sweep, and a
threshold written against no example is a guess.

## Trail

- 2026-09-11: opened by the close of
  [R-540](540-the-judged-rate-and-the-hand-column-are-compared-on-a-probe-and-no-sweep.md), whose
  sweep-columns addendum names the sixteen runs.
