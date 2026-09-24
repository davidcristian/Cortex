# A turn nobody escalated completes under whatever id the inner runner used

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0046](../../adr/ADR-0046-work-identities-on-log-lines.md)
**Verified:** 2026-09-24
**Trigger:** either half of the agreement moves: `EscalatingTurnEngine(` gains a construction site
other than the one in `cortex_orchestrator/engines.py`, or that site's factory returns anything but
`self._turn_engine(...)`; or `TurnEngine.handle_turn` in `cortex_core/engine.py` stops completing
with `TurnCompleted(turn_id=turn_id, ...)`, the id it was handed. Both are a grep. The path only
runs with `CORTEX_ESCALATION` on, since with it off `for_stream` returns the plain engine and no
wrapper exists.

`EscalatingTurnEngine` in `brain/packages/core/src/cortex_core/escalating_engine.py` holds the id
from its first statement and completes an escalated turn under it. Its other exit does not. When
the cortex asked for nothing, the wrapper passes the inner runner's own `TurnCompleted` object
through unchanged, so the id the client reads on that path is whatever the inner runner put on it.

The two agree today: the wrapper passes the id down on the call and the one engine behind
`make_inner` returns it. So this is a rule resting on an agreement between two files rather than on
the one statement that could enforce it, on the path that runs for every turn that is not
escalated. The transparent path has a test, but its fake inner runner completes under the same id
the wrapper was handed, so nothing fails when the two disagree.

Re-emitting under the wrapper's id on the transparent path means building a new `TurnCompleted` and
choosing what to do with the text on it, which is the inner runner's accumulated reply rather than
the wrapper's `parts`. The two are equal on that path and saying so is a third rule, so the fix is
either a rebuild that duplicates the inner's text or an assertion that the ids match, and which is
right depends on whether a second runner ever sits behind `make_inner`.

## History

- 2026-08-20: Opened by a review of the turn id move, which fixed the escalating path of this
  wrapper and left the transparent path reading its identity out of the runner it wraps.
- 2026-09-10: The trigger has not fired and the agreement still holds between the same two files.
  `EscalatingTurnEngine.handle_turn` still ends its unescalated path with a bare `yield completed`,
  and the only runner behind `make_inner` is the `TurnEngine` the orchestrator's `engines.py`
  builds, whose own completion is `TurnCompleted(turn_id=turn_id, ...)` with the id it was handed.
- 2026-09-17: Not fired, and the agreement is where it was. `escalating_engine.py` still ends the
  unescalated path with `yield completed` (line 76) and completes an escalated one under its own id
  (line 88); `engines.py` line 139 is the only `EscalatingTurnEngine(` in any `src` tree and its
  factory is still `self._turn_engine(...)`; and `engine.py` line 209 still completes with the id
  it was handed. The claim that the fix tested only the escalating path was loose:
  `test_a_turn_that_does_not_escalate_is_passed_through_unchanged` covers the transparent path, but
  its completion has `harness.TURN`, the id the wrapper was handed, so it cannot tell pass-through
  from re-emission. The case beside it is still named
  `test_the_wrapper_hands_the_conductor_the_turn_id_the_inner_engine_minted`, with a docstring
  saying only the engine knows the id, which the id move made false; the fix should rename it. The
  trigger now names the grep that decides it and the setting without which the path never runs.
- 2026-09-24: Not fired. Three commits of this date rewrote the construction site in `engines.py`,
  which now hands the inner engine a `HandoffAheadBackend`, and two of them touched both engine
  files; the factory is still `self._turn_engine(...)`. `engines.py:106` is still the only
  `EscalatingTurnEngine(` in any `src` tree, `escalating_engine.py` still ends the unescalated path
  with `yield completed` (line 49) and completes an escalated one under its own id (line 62), and
  `engine.py:126` still completes with the id it was handed. Both tests named above still exist
  under their names.
