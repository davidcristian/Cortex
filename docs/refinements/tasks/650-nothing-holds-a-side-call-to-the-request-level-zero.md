# Nothing holds a new side call to the request-level zero the shipped bounds carry

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-17
**Trigger:** a `GenerationBounds` call in `brain/packages/*/src` that spells `thinking=False` and no
`trace_tokens`, read with `grep -rn 'thinking=False' brain/packages/*/src --include=*.py`. Today
that grep prints seven lines: the three bounds named below and four lines of docstring or comment
prose. A further code line fires it when its call names no `trace_tokens`, whether it is a fourth
side call or `SubagentAttempt`'s bound gaining the switch.

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

**A cheaper holder than a twelfth scan, noted 2026-09-17.** The rule reads only brain sources, so a
brain test can carry it: a test under `brain/packages/core/tests/` that parses every file under
`brain/packages/*/src` with `ast` and fails on a `GenerationBounds` call passing `thinking=False`
without `trace_tokens`. It runs inside `just check` already, and it adds no roster line to
`AGENTS.md`, the documentation index or the workflow, which a new cross-tree scan would. What it
gives up is the scan's place beside the other gates that read the tree without importing it. The
two readings agree on the three bounds today, and the choice between them belongs to whoever
closes this entry.

## Trail

- 2026-09-12: opened by the close of
  [R-466](466-nothing-holds-a-cap-to-a-bounded-trace.md), which was declined on the argument that the
  request now carries the bound the pairing rule needs and that the tier flag a gate would read is
  deliberately unbounded on the tier a user's reply shares. The readings behind that close are in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) addendum of this date.
- 2026-09-17: read against the tree and not fired. `GenerationBounds(` appears on six lines under
  `brain/packages/*/src`: the three bounds this entry names (`TITLE_BOUNDS` at
  `cortex_core/session_title.py:56`, `RECAP_BOUNDS` at `cortex_core/recap_prompt.py:49`, and
  `rank_bounds` at `cortex_core/rerank_judge.py:118`, whose keywords sit on the lines below), the
  cap-only bound in `SubagentAttempt` at `cortex_core/subagent_attempt.py:131`, the rendered bound in
  `ReplyBoundsConfig` at `cortex_orchestrator/config_reply.py:105`, which passes `thinking` as a
  variable, and one docstring line in `cortex_core/drain.py`. Each of the three is still pinned by
  its own test (`test_sessions.py:198`, `test_summarizing.py:650`, `test_rerank_judge.py:308`), and
  `drain_text` still has exactly those three callers. The trigger's second half, a cap added to a
  bound that has none, named no bound: every `thinking=False` bound in the tree already has a cap.
  The trigger is restated as the grep that decides it, and a test-shaped holder is recorded beside
  the scan.
