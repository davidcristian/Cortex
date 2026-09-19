# Live contract runs shared the brain's Redis keyspace

**Status:** done 2026-08-03
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Found and fixed on the same day, so this is a record rather than waiting work.

The live session checks read a fixed recency window with fixture dates in the past, so real
sessions more recent than the fixtures push them out of the window. A review on 2026-07-14 noted
this and sized it against a `limit=50` window, meaning fifty real sessions before it would matter.
Two days later another change added a `limit=3` check resting on the same assumption, which
lowered the threshold from fifty to three, and nobody updated the record. So the problem was
latent from 2026-07-16 and failing in practice from the day the compose Redis first held three
real sessions dated after the fixtures, which its oldest surviving session puts at 2026-07-21 or
earlier. Nothing reported it, because these suites are run by hand. Reproduced on 2026-08-03 with
sixteen real sessions present.

Fixed by giving the live runs a Redis logical database of their own
(`brain/packages/session/tests/live_redis.py`, database 15, which production never selects),
emptied before the suite and after every check, so every check starts from the empty store the
fakeredis fixture already provides. That also fixed two siblings with the opposite symptom: the
schedule and handoff live suites used to skip whenever the shared database held a real record,
passing while asserting nothing, and both skips are gone because that database holds nothing real
to protect. The key-prefix scans went with them, and with them a duplicate of each adapter's key
layout inside the test.

The lesson: a recorded residue is sized against the code that existed when it was written, and a
later change can lower its threshold without anyone reading it again.

## History

- 2026-08-03: Found and fixed the same day. The residue had been recorded on 2026-07-14 against a
  `limit=50` window, lowered to three two days later without being resized, latent since
  2026-07-16 and failing in practice once the compose Redis held three real sessions dated after
  the fixtures. The live runs now select Redis database 15 and empty it before the suite and after
  every check, which also removed two sibling suites' skips and the key-prefix scans.
