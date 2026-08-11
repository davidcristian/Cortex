# The Intel NPU as a third placement target

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** A feasibility pass over the two unknowns the entry names.

A future OpenVINO `InferenceBackend` adapter + a
`PlacementTarget.NPU`, pending a feasibility pass. Using the otherwise-idle NPU for tiny
subagents or embeddings serves the same "keep the machine usable" motivation as the caps above,
and OpenVINO GenAI is the engine because llama.cpp has no NPU path. The hardware is **present**
(an Intel Core Ultra 9 275HX, confirmed 2026-07-01), so two unknowns decide it: (a) whether the
NPU is reachable from the dockerized WSL2 brain at all, the likely blocker, since WSL2
paravirtualizes the dGPU but not the NPU, so it may force a host-side runtime that crosses the
dockerized-brain seam; and (b) whether NPU inference for a 2-4B model is fast and mature enough
to be worth a target. **The two unknowns and the hardware confirmation moved here from the
ROADMAP's Slice 8.5 block on 2026-07-19**, where they were the only record of either; the
deferral itself has been recorded here and at its origin ADR since the extraction.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section.
- 2026-07-19: The two unknowns and the hardware confirmation moved here from the ROADMAP's Slice 8.5
  block, where they were the only record of either.
- 2026-07-19: It stayed in this backlog when host-side work was extracted to
  [docs/host/](../../host/index.md), because the work itself is code even where only the host's
  hardware can judge the result, and moving it would split a design decision from its area.
