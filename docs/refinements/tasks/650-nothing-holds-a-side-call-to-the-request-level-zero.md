# Nothing holds a new side call to the request-level zero the shipped bounds carry

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-12
**Trigger:** the next shipped `GenerationBounds` that names a `max_tokens` and `thinking=False`
without a `trace_tokens`, which is a fourth in-turn side call or a cap added to a bound that has
none today.

Opened 2026-09-12 by the close of
[R-466](466-nothing-holds-a-cap-to-a-bounded-trace.md), whose own candidates were declined and which
left this narrower half: the shape is written by hand three times and held nowhere.

`RECAP_BOUNDS`, `TITLE_BOUNDS` and `rank_bounds(k)` each pair a cap with `thinking=False` and
`trace_tokens=0`, and the zero is the half that bounds the trace where the engine reads the key. Each
is pinned by its own test, so none can lose the zero quietly. A fourth caller is what nothing covers:
it would arrive with its own test, and a test written beside a bound asserts what that bound says
rather than what it should have said.

**Why this is the tractable half.** The precondition [R-466](466-nothing-holds-a-cap-to-a-bounded-trace.md)
wanted held is whether a tier's trace is bounded, which is the deployment's argv and is invisible to
the core by design. This one is a fact about how a call is written, which any reader of the tree can
check. A constructor-level rule is still refuted, and by one caller each: `SubagentAttempt` names a
cap with no switch and rests on the flags its tier is started with, and `ReplyBoundsConfig` renders a
deployment's own cap with the switch it was given, so a `__post_init__` that raised on a cap without a
count would reject one caller that is safe and one configuration that is a person's choice.

**What would close it.** A scan over the bounds this tree itself writes: every `GenerationBounds` call
in `brain/packages/*/src/` that names `max_tokens` and `thinking=False` also names `trace_tokens`,
read out of the syntax rather than by importing anything, the way `moduleconstants.py` reads a
module's top level. That is a new gate with everything a gate carries, its roster line in the
contract, the scan list in the documentation index and the workflow comment, and a mutation table. The
cheaper alternative is a named constructor for the shape, so the three calls and any fourth read as
one decision, which makes the right thing easy and holds nothing; it is worth doing only alongside the
scan or not at all.

## Trail

- 2026-09-12: opened by the close of
  [R-466](466-nothing-holds-a-cap-to-a-bounded-trace.md), which was declined on the argument that the
  request now carries the bound the pairing rule needs and that the tier flag a gate would read is
  deliberately unbounded on the tier a user's reply shares. The readings behind that close are in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) addendum of this date.
