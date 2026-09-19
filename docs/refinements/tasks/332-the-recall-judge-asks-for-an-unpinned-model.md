# The recall judge asks for a model id no test checks

**Status:** done 2026-09-11
**Area:** memory
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)

[R-298](298-served-ids-are-opt-in-everywhere.md) added tests for three of the four callers that
name a model id in the composition root and left the fourth.

`build_memory` takes `runtime.cortex_model` and hands it to `JudgeRecallPolicy`, which asks the
resident model to rank a recall pool. A wrong id there is not a failed turn: `select` catches
`InferenceError` and falls back to the unjudged ranking, and a lease refused for an id the
deployment does not host arrives as exactly that error, so the whole capability would degrade to
what `CORTEX_MEMORY_RECALL=raw` does, on every recalling turn, recorded once per recall in a
warning nobody is watching. The three tests that exist all catch a loud failure; this one catches a
quiet one, and it costs more because the fixture has to wire memory.

The test is the same shape as the three: rename the tier, run the caller against a deployment that
hosts the renamed one, and assert the judged ranking rather than the fallback. Asserting the judged
ranking means scripting a backend that answers a rank envelope, so the fixture is a fake with an
opinion rather than a refused socket.

Two heavier options stay available. The fakes could take the id from the wiring under test rather
than from the test author. Or the eighteen hand-written backends could collapse onto the twin, one
place to teach and `serves` included, at the cost of the per-file shapes some of them assert on.
Neither is worth doing for one caller.

Re-counted 2026-09-11: there were five such callers on the day this was opened, and six now, three
of them tested. The recap summarizer has taken `runtime.cortex_model` in `window_builders.py` since
2026-08-06 and hands it to every `drain_text` call in `summarizing.py`, where `InferenceError` is
caught, a warning is written and the plain window is returned, so a refused lease there degrades
every recap quietly. And the trace setting's probe, `resolve_trace_lever` in `builders.py` since
2026-08-29, posts the same id in the `model` field of its one request and reads any refusal that
does not quote the budget key as a build without the setting, so on a server that routes by id a
wrong id costs the deployment that setting for the whole run, on one info line. Neither has a test
that renames the tier.

## History

- 2026-08-20: Opened by the close that tested the resident tier, the deep tier and the subagent
  roster's default, and named this one as what those three do not reach. Recorded as ADR-0068
  decision 9.
- 2026-09-11: Re-filed as actionable. The trigger's second half fired on 2026-08-29, when the trace
  setting's probe arrived as a configured caller of `cortex_model` with four tests and none that
  renames the tier, and the re-count found the recap summarizer had been a fifth untested caller
  since before the entry was opened. The judge is still wired as described, `build_memory` handing
  `cortex_model` to `JudgeRecallPolicy` through `recall_policy_from_config`, `select` catching
  `InferenceError` and falling back on a warning, and the one wiring test asserting the type it
  builds and no id.
- 2026-09-11: Fixed as three tests in `test_wiring`, each driving the builder under a renamed tier
  over a backend that serves the renamed one alone: `build_memory` recalling over a scripted
  result, `build_history_window` folding a recap, and `build_inference_backend` against a loopback
  server that routes by id, with the budget asserted on the wire. Proved by five mis-wirings over
  the orchestrator, core and inference suites, the two pass-through cases having caught a first
  draft that tested the interfaces beneath the builders. A boot check was weighed and not built,
  since every caller reads the one config field (ADR-0068 decision 9).
