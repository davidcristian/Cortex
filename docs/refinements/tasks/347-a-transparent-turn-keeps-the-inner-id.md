# A turn nobody escalated completes under whatever id the inner runner claimed

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** an inner runner that completes under an id other than the one it was handed, meaning a
second `TurnRunner` behind `make_inner` or a change that gives an engine back its own id factory.

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
that is not escalated, which is most of them. The change that fixed the escalating arm added a test
for that arm only, so nothing in the suite fails when the transparent arm disagrees.

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
