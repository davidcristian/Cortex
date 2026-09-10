# The recall judge asks for a model id nothing pins

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)

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

**Re-counted 2026-09-11: there were five such callers on the day this was opened, and there are
six now, three of them pinned.** The recap summarizer has taken `runtime.cortex_model` in
`window_builders.py` since 2026-08-06 and hands it to every `drain_text` call in `summarizing.py`,
where `InferenceError` is caught, a warning is written and the plain window is returned, so a
refused lease there degrades every recap quietly exactly as the judge's degrades every recall;
the close that opened this entry did not count it. And the trace-lever probe, `resolve_trace_lever`
in `builders.py` since 2026-08-29, posts the same id in the `model` field of its one request to
the endpoint and reads any refusal that does not quote the budget key as a build without the
lever, so on a server that routes by id a wrong id costs the deployment its lever for the whole
run, on one info line. Neither has a test that renames the tier. The second of them is the
trigger's other half, a configured caller arriving without a pin, so the entry is actionable: the
three pins that landed are the shape, and the three unpinned callers, the judge, the recap and the
lever, are the work.

## Trail

- 2026-08-20: Opened by the close that pinned the resident tier, the deep tier and the subagent
  roster's default, and named this one as what those three do not reach. Recorded in the ADR-0001
  configured-caller addendum.
- 2026-09-11: re-filed as actionable. The trigger's second arm fired on 2026-08-29, when the
  trace-lever probe arrived as a configured caller of `cortex_model` with four tests and none that
  renames the tier, and the re-count found the recap summarizer had been a fifth unpinned caller
  since before the entry was opened. The judge is still wired as described, `build_memory`
  handing `cortex_model` to `JudgeRecallPolicy` through `recall_policy_from_config`, `select`
  catching `InferenceError` and falling back on a warning, and the one wiring test asserting the
  type it builds and no id. Recorded in the origin decision's addendum of the same day.
