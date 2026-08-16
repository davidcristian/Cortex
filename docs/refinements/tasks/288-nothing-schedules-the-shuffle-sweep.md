# Nothing schedules the shuffle sweep

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** an order dependency found by a hand-run sweep that the standing seed had already run past, which is the case the standing gate provably cannot draw.

Opened 2026-08-16 by the decision to make the shuffle standing under a fixed seed rather than a
per-run one ([ADR-0002 shuffle addendum](../../adr/ADR-0002-toolchain-gates.md)). That decision
rests on a measured property of `pytest-randomly`: the order under a fixed seed is per item and
stable, so a test added today draws its position once against everything already there, and a pair
that already coexists under the frozen order keeps the order it has forever. The half that buys is
a gate whose red always reproduces. The half it costs is that the pairs already in the tree are
never re-drawn.

`just shuffle [seed]` is where they get re-drawn, and nothing runs it. It is not in `just check`
by design, since its whole point is an order nobody chose, and it is deliberately absent from CI
for the same reason. So the sweep happens exactly when a person remembers it, which is the same
mechanism this entry's own origin spent four weeks demonstrating the weakness of: the hand-run
measurement was re-derived three times by three passes that each had to read how the last one did
it.

**What would close it, and why none of it was taken now.** A scheduled CI job (weekly, or on a
release) would run the sweep on somebody else's clock, at the cost of a red that arrives detached
from any commit and of a workflow that is not the `just check` mirror every other job here is. A
`just check` variant that draws a random seed once a day and caches it would keep the gate
reproducible within a day and shuffle across days, at the cost of a cache file the gate has to read
and fail closed on. Rotating the frozen seed on a schedule is the cheapest of the three and the
most dishonest, since a seed committed as a constant that somebody bumps periodically is a per-run
lottery with extra steps and a diff. All three are worth less than the first evidence that the
standing draw actually missed something, which is the trigger above.
