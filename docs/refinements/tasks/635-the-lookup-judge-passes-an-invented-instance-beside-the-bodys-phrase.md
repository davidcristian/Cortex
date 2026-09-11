# The lookup judge passes an invented instance beside the body's phrase

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-09-11 by the close of
[R-540](540-the-judged-rate-and-the-hand-column-are-compared-on-a-probe-and-no-sweep.md).
`names_the_period` in `scripts/envelopejudges.py` reads whether the body's own unit and instance
appear in the reply, and a reply that quotes them on its way to asserting something else passes.
On a full sweep of `Qwen3.5-0.8B` that was 16 of 96 lookup runs: the clinic body says `month
ending` and names no month, and the reply quoted the phrase beside December, February 26th to 30th,
October 2016, January 2010 or the second half of the month; the fleet and network bodies drew a
fiscal year and a span of fortnights 18 through 19 beside their own phrase. Nine of the sixteen
are on the raw arm, so the control cell reads 31 of 32 where a reader gives it 22.

**What would close it.** A rule that refuses a reply naming an instance the body does not state
beside the one it does: a second month, a calendar date, a year, or a second numbered period of
the same unit. The charitable naming column is unaffected, since it reads the unit and a nearby
number rather than a quotation. What makes it a decision rather than a patch is the clinic body:
it names a unit and no instance, so the judge has to say what a right answer to an underspecified
question looks like, and that is where the threshold this entry defers lives.

**Why it was left.** The same sitting, the same runway, and a rule for the underspecified body
written against one pick's replies would be the guess the judged-delivery addendum refused.

## Trail

- 2026-09-11: opened by the close of
  [R-540](540-the-judged-rate-and-the-hand-column-are-compared-on-a-probe-and-no-sweep.md), whose
  sweep-columns addendum names the sixteen runs.
