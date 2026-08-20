# The Intel NPU as a third placement target

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** An NPU device enumerating from inside a container, meaning
`Core().get_property("NPU", "AVAILABLE_DEVICES")` answers with anything at all.

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

**Probed 2026-08-20 and re-triggered rather than closed** ([ADR-0012](../../adr/ADR-0012-resource-governance.md)
NPU-probe addendum). Unknown (a) is answered and the guess about why was right, and the answer
distinguishes three claims that wear one sentence. **Measured at the guest:** the only device node
is `/dev/dxg`, `/dev/accel` and `/dev/dri` do not exist, the PCI bus carries no Intel silicon at
all, and the kernel is built `# CONFIG_DRM_ACCEL is not set`, so `intel_vpu` could not bind a
device it was handed. **Measured at the paravirtualization:** `libdxcore.so` enumerates exactly two
adapters, the discrete GPU and the integrated one, under every capability attribute including the
generic ML one, and both answer to the GPU hardware type while neither answers to the compute
accelerator or NPU one. **Measured from a container:** OpenVINO's NPU plugin ships in the wheel and
loads, and it enumerates nothing, `available_devices` reading `['CPU']` and the plugin's own
`AVAILABLE_DEVICES` reading `[]`. **Not measured:** whether the machine has an NPU at all. The CPU
model is the one named above and the Windows driver store carries Intel's NPU package, in two
staged versions both covering the Arrow Lake id `8086:AD1D`, but a staged package is not a present
device and this guest cannot see Windows device state, interop being off. One finding reaches past
today's kernel: of the 1,038 Windows driver packages WSL maps in, exactly three ship Linux user
mode libraries, the Intel graphics package in its two staged versions and the NVIDIA one, while
both NPU packages ship only Windows DLLs. So the condition that revives this work has two halves,
WSL projecting the device and the vendor shipping a Linux driver for it, which is why the trigger
is now the one command that needs both. Unknown (b) is untouched, there being nothing to measure
it on.

## Trail

- 2026-08-20: Three counts above corrected against the driver store as it stands. The denominator
  is 1,038 package directories, not the 1,349 entries `ls` reports, the rest being 311 `.ini`
  sidecars; the Intel graphics package is counted in its two staged versions, which is what makes
  three ship a `.so` while only two vendors do; and the NPU package is staged twice as well.
- 2026-08-20: Probed and re-triggered rather than closed. The blocker the entry named is confirmed
  at the guest and at the container both, and the trigger moves from a feasibility pass, which this
  was, to the state of the world that would make rerunning it worthwhile.
- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section.
- 2026-07-19: The two unknowns and the hardware confirmation moved here from the ROADMAP's Slice 8.5
  block, where they were the only record of either.
- 2026-07-19: It stayed in this backlog when host-side work was extracted to
  [docs/host/](../../host/index.md), because the work itself is code even where only the host's
  hardware can judge the result, and moving it would split a design decision from its area.
