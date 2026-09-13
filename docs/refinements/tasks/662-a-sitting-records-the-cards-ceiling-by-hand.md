# A sitting records the card's ceiling by hand

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-13

Opened 2026-09-13 by the sitting that gave every injection arm a token total and read the card's
ceiling at idle (the
[ADR-0029 idle-ceiling addendum](../../adr/ADR-0029-vision-screen-capture.md)).

An arm now prints what it generated, so a stopped row leaves its own token count in the run log. The
other half of a price is the ceiling those tokens were generated under, and that half is still taken
by hand: the runbook tells an operator to read `enforced.power.limit` against `power.max_limit`
before starting and again while the row serves, and nothing fails when they do not. Two sittings in
a row were priced with no ceiling recorded beside them.

**Trigger:** a row's token total is published with no card reading beside it, or a published figure
has to be re-read later against a clock nobody wrote down.

**What would close it.** The harness already shells out to docker through `_docker`, and its own
`cortex-inj-probe` container runs an image carrying `nvidia-smi`, so one
`docker exec` reading `clocks.sm,power.draw,enforced.power.limit,power.max_limit` at the start and
end of a row would put both halves of the price on the same line as the tokens. The reading costs a
single call per row and fails nothing on its own, which is the point: a row that prints its ceiling
cannot be published without one.

Two things this deliberately does not do. It does not read the card from inside a test assertion,
since a clock is a property of the sitting rather than of the behaviour under test. And it does not
refuse a capped card, because a row drawn under a lowered ceiling is still a row, so long as the
ceiling it ran under is recorded beside its cost.

## Trail

- 2026-09-13: opened by the sitting that gave every arm a token total, and left open here with a
  measurement that raises what it is worth. The card was read twice more the same day with nothing
  running, and the ceiling moved: at 09:38, after a night of unattended work with the display
  asleep, the enforced limit stood under a third of the card's maximum and under three fifths of its
  default, and at 12:53, with the desktop session awake, it stood above nine tenths of the maximum
  and above the default (the
  [ADR-0029 moving-ceiling addendum](../../adr/ADR-0029-vision-screen-capture.md)). A hand-taken
  reading an operator can skip was already a gap; a ceiling that differs between two sittings on one
  day means a row published without one cannot be priced afterwards at all. The second half of the
  trigger has fired: the loads rows the runbook publishes for 2026-09-13 carry costs with no ceiling
  beside them, and the best that can be said of them now is that the whole night ran under the
  lowered one. The entry stays open because closing it is a change to the live harness, which this
  sitting did not take on.
