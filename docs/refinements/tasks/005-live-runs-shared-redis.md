# Live contract runs sharing the brain's Redis keyspace

**Status:** landed 2026-08-03
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Found and closed the same day, 2026-08-03, so it is recorded here as what it was rather than as
work waiting. This is not a new deferral so much as an old one that had been mis-sized: the
[ADR-0021 sweep addendum](../../adr/ADR-0021-session-read-seam.md) recorded on 2026-07-14 that the
live session checks read a fixed recency window with fixture dates in the past, so real sessions
more recent than those crowd them out, and it sized the residual against a `limit=50` window,
meaning fifty real sessions before it would bite. Two days later the pinning addendum landed a
`limit=3` check on the same assumption and the trigger silently fell from fifty to three; the
residual was not resized, and the entry in
[session-read-seam.md](../index.md#session-read-seam) still carried the fifty. So it had been latent
since 2026-07-16 and failing in practice since the compose Redis first held three real sessions
dated after the fixtures, which its oldest surviving one puts at 2026-07-21 or earlier: roughly
a fortnight of a live run that would have blamed a correct adapter, unnoticed because these
suites are run by hand. Reproduced on 2026-08-03 with sixteen real sessions present. **What it
became:** the live runs select a Redis logical database of their own
(`brain/packages/session/tests/live_redis.py`, database 15, which production never selects) and
empty it before the suite and after every check, so every check starts from the empty store the
fakeredis fixture already gives it. That also closed two siblings of the same defect wearing the
other mask: the schedule and handoff live suites used to **skip** whenever the shared database
held a real record, reporting green while asserting nothing, and both skips are gone because
there is nothing real in that database to protect. The prefix sweeps went with them, and with
them a coupling that restated each adapter's key layout inside the test. Decision, rejected
alternatives, and evidence in the
[ADR-0002 addendum on the live-run database](../../adr/ADR-0002-toolchain-gates.md). The lesson
worth keeping is the one this entry is filed under: a recorded residual is sized against the
code that existed when it was written, and a later change can lower its trigger without anyone
reading it again.

## Trail

- 2026-08-03: Found and closed the same day, so the record is of what it was rather than of work
  waiting. It was an old residual that had been mis-sized: recorded on 2026-07-14 against a
  `limit=50` window, silently lowered to three two days later by the pinning addendum without
  being resized, latent since 2026-07-16 and failing in practice since the compose Redis first
  held three real sessions dated after the fixtures. The live runs now select Redis database 15
  and empty it before the suite and after every check, which also removed two sibling suites'
  skips and the prefix sweeps. The session-read seam's own fixed-window residual is recorded as
  closing with it.
