# A turn nobody escalated completes under whatever id the inner runner claimed

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-17
**Trigger:** either half of the agreement moves: `EscalatingTurnEngine(` gains a construction site
other than the one in `cortex_orchestrator/engines.py`, or that site's factory returns anything but
`self._turn_engine(...)`; or `TurnEngine.handle_turn` in `cortex_core/engine.py` stops completing
with `TurnCompleted(turn_id=turn_id, ...)`, the id it was handed. Both are a grep. The arm only runs
with `CORTEX_ESCALATION` on, since with it off `for_stream` returns the plain engine and no wrapper
exists.

Opened 2026-08-20 by a review of the change that moved the turn id out of the engine and into the
caller that schedules the turn. `EscalatingTurnEngine` in
`brain/packages/core/src/cortex_core/escalating_engine.py` now holds the id from its first statement
and completes an escalated turn under it. Its other exit does not. When the cortex asked for nothing,
the wrapper yields the inner runner's own `TurnCompleted` object through unchanged, so the id the
client reads on that path is whatever the inner runner put on it and not the one the wrapper was
asked to serve.

The two agree today, and provably: the wrapper passes the id down on the call and the one engine
behind `make_inner` echoes it back. So this is an invariant resting on an agreement between two
files rather than on the one statement that could enforce it, in the arm that runs on every turn
that is not escalated, which is most of them. The transparent arm has a test, but its fake inner
runner completes under the same id the wrapper was handed, so nothing in the suite fails when the
two disagree.

**Why it is not simply fixed now.** Re-emitting under the wrapper's id on the transparent path would
mean building a new `TurnCompleted` and choosing what to do with the text on it, which is the inner
runner's accumulated reply rather than the wrapper's `parts`. The two are equal on that path and
saying so is a third invariant, so the fix is either a rebuild that duplicates the inner's text or
an assertion that the ids match, and which of those is right depends on whether a second runner ever
sits behind `make_inner`. That is the trigger.

**What would close it.** Either the wrapper completes under its own id on both arms, with a case
pinning that a completion carrying a foreign id does not reach the client, or the pass through is
stated as deliberate at the `yield` with the agreement it rests on written beside it, so the next
runner behind that factory reads the constraint before it breaks it.

## Trail

- 2026-08-20: opened by a review of the turn id move, which fixed the escalating arm of this wrapper
  and left the transparent arm reading its identity out of the runner it wraps.
- 2026-09-10: the trigger has not fired and the agreement still holds between the same two files.
  `EscalatingTurnEngine.handle_turn` still ends its unescalated arm with a bare `yield completed`,
  and the only runner behind `make_inner` is the `TurnEngine` the orchestrator's `engines.py`
  builds, whose own completion is `TurnCompleted(turn_id=turn_id, ...)` with the id it was handed.
  So there is still one runner on that path and it still echoes the id, which is the agreement this
  entry says nothing enforces.
- 2026-09-17: not fired, and the agreement is where it was. `escalating_engine.py` still ends the
  unescalated arm with `yield completed` (line 76) and completes an escalated one under its own id
  (line 88); `engines.py` line 139 is the only `EscalatingTurnEngine(` in any `src` tree and its
  factory is still `self._turn_engine(...)`; and `engine.py` line 209 still completes with the id it
  was handed. The body's claim that the fix tested only the escalating arm was loose:
  `test_a_turn_that_does_not_escalate_is_passed_through_unchanged` covers the transparent arm, but
  its completion carries `harness.TURN`, the id the wrapper was handed, so it cannot tell pass
  through from re-emission. The case beside it is still named
  `test_the_wrapper_hands_the_conductor_the_turn_id_the_inner_engine_minted`, with a docstring
  saying only the engine knows the id, which the id move made false; the fix should rename it. The
  trigger now names the grep that decides it and the setting without which the arm never runs.
