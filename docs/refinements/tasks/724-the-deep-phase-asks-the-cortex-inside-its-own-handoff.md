# The deep phase asks the cortex inside its own handoff

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-24

`StreamEngines.for_stream` (`cortex_orchestrator/engines.py`) builds the deep model's phase from
the stream's own capabilities with `replace(caps, escalation=None, tools=...)`, so the phase keeps
the cortex turn's `memory` and `window`. `BrainPhase.run` (`cortex_core/brain_phase.py`) passes
them to `assemble_inference_messages` inside the handoff's residency scope. With memory on and the
default `judge` recall, a recall that finds any candidate asks the cortex to rank it
(`JudgeRecallPolicy`, built over `runtime.cortex_model`), and that call waits for the scope to
end, which cannot happen before the phase returns. The deep model is never asked, the turn does
not end, and the card stays with the deep model. The recap of a history over its window's budget
asks the cortex the same way (`build_history_window` passes `runtime.cortex_model`); that path was
read, not run.

A probe against the fakes shows the recall case: an escalating turn over one stored memory and a
backend that leases through the `SwappingModelManager` makes three cortex requests and none to the
deep model, and is still waiting 5 s later. It waits the same way with the backend the root wired
before a stream's calls went through `HandoffAheadBackend`; through it, the wait is announced as
another request's handoff, which names the wrong handoff.

Neither remedy is built: give the phase a recall and a window that ask the deep model, which is
the resident during the phase, or ones that ask no model (the `raw` policy and no recap).

## History

- 2026-09-24: Opened by the change that announces a wait behind another turn's handoff before
  every model call of a stream, whose probe of an escalating turn with memory on found the deep
  phase waiting on its own handoff.
