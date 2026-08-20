# The recall judge asks for a model id nothing pins

**Status:** open, fix when it bites
**Area:** memory
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)
**Trigger:** the first deployment whose recall goes flat with `CORTEX_MEMORY_RECALL=judge` set, or
the next configured caller of a model id arriving without a pin of its own.

Opened 2026-08-20 by the close of [R-298](298-served-ids-are-opt-in-everywhere.md), which pinned
three of the four callers that name a model id in the composition root and left the fourth.

`build_memory` takes `runtime.cortex_model` and hands it to `JudgeRecallPolicy`, which asks the
resident model to rank a recall pool. That caller is the one where a wrong id is not a failed turn.
`select` catches `InferenceError` and falls back to the unjudged ranking, and a lease refused for
an id the deployment does not host arrives as exactly that error, so the whole capability would
degrade to what `CORTEX_MEMORY_RECALL=raw` does, on every recalling turn, for ever, recorded once
per recall in a warning nobody is watching. The three pins that landed all catch a loud failure;
this one would catch a quiet one, which is the better reason to have it and the reason it is not
free: the fixture has to wire memory, which the other three did not need.

The shape is the same as the three: rename the tier, run the caller against a deployment that
hosts the renamed one, and assert the judged ranking rather than the fallback. What makes it cost
more is that asserting the judged ranking means scripting a backend that answers a rank envelope,
so the fixture is a fake with an opinion rather than a refused socket.

The two heavier shapes [R-298](298-served-ids-are-opt-in-everywhere.md) weighed stay unchosen and
stay available. The fakes could take the id from the wiring under test rather than from the test
author, which is what a config-driven caller's fixture would grow anyway. Or the eighteen
hand-rolled backends could collapse onto the twin, one place to teach and `serves` included, at the
cost of the per-file shapes some of them assert on. Neither is worth doing for one caller; both
become worth weighing again if a second unpinned caller appears, which is the other half of the
trigger.

## Trail

- 2026-08-20: Opened by the close that pinned the resident tier, the deep tier and the subagent
  roster's default, and named this one as what those three do not reach. Recorded in the ADR-0001
  configured-caller addendum.
