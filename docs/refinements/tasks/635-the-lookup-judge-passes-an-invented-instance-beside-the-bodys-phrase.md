# The lookup check passes an invented instance beside the body's phrase

**Status:** done 2026-09-11
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

`names_the_period` in `scripts/envelopejudges.py` reads whether the body's own unit and instance
appear in the reply, so a reply that quotes them on its way to asserting something else passed. On a
full review of `Qwen3.5-0.8B` that was 16 of 96 lookup replies: the clinic body says `month ending`
and names no month, and the reply quoted the phrase beside December, February 26th to 30th, October
2016, January 2010 or the second half of the month, while the fleet and network bodies drew a fiscal
year and a span of fortnights 18 through 19 beside their own phrase. Nine of the sixteen are on the
raw variant, so the control cell read 31 of 32 where a reader gives it 22.

The decision behind the fix is what a right answer to an underspecified question looks like: the
clinic body names a unit and no instance, so the rule has to say that a right answer names the
month-ending period and no month, year or day of its own.

**What closed it.** `invents` in `scripts/envelopejudges.py` reads a capitalised month, a year, a
day ordinal and a numbered period of the body's unit, and counts one invented when the body does not
state it, the body's own period number aside. `names_the_period` refuses such a reply under both
columns.

## History

- 2026-09-11: opened by the close of
  [R-540](540-the-judged-rate-and-hand-read-column-are-compared-on-one-probe.md), whose
  reader-column review of the smallest pick names the sixteen replies. A rule for the
  underspecified body written against one pick's replies would have been the guess the delivery
  rule refused.
- 2026-09-11: done. This entry's claim that the charitable naming column was unaffected was wrong:
  it passed all 16 named replies, so it is checked too. The rule refuses 14 of the 16; the two it
  passes answer with `the second half of the month`, a span the body states in another role, filed
  in [R-639](639-the-envelope-judges-read-no-form.md). None of the six replies the strict naming
  fails changes result under either column. It also refuses 12 replies the reader kept, each naming
  an instance its body does not state beside the right period, and the 0.8B lookup control cell
  falls to 21 of 32, under the floor. Both are recorded with the rule change at the origin.
