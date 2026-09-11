# The Intel NPU as a third placement target

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** An NPU device enumerating from inside a container, meaning
`Core().get_property("NPU", "AVAILABLE_DEVICES")` answers with anything at all. That is one
container run: `pip install openvino` over `python:3.12-slim`, with `/dev/dxg` and `/usr/lib/wsl`
handed in, then read `available_devices` and that property. This entry's trail records what the run
answered when it was last taken, and the body records which half of the condition is already
satisfied.
**Verified:** 2026-09-11

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
distinguishes three claims that share one sentence. **Measured at the guest:** the only device node
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
is the one command that needs both. Unknown (b) is untouched, there being nothing to measure
it on.

**Re-read 2026-09-08, and the projection half of that condition is already met.** The adapter list
is not the whole of what the paravirtualization carries. `D3DKMTEnumAdapters2` asked for a count
answers **three** where the list it fills carries two, a buffer sized for fewer than three is
refused outright, and the adapter the list omits opens by LUID and describes itself: host PCI
address `00:0B.0`, no dedicated video memory, and an adapter type of `0x2881`, whose set bits are
render, paravirtualized and **compute only**. `00:0B.0` is where Intel's NPU sits on this CPU
generation, and this record already carries the driver store's `npu.inf` of class
`ComputeAccelerator` covering the Arrow Lake id, so calling that adapter the NPU is an inference
from the address, the type and those packages rather than a reading of Windows device state, which
this guest still cannot take. It is also the strongest evidence yet for the line this entry has
kept as unmeasured, whether the machine has an NPU at all. What it changes is which half of the
condition is outstanding: WSL does project the device, so what is missing is the Linux user mode
driver, exactly the half the driver-store count above says no vendor ships. The count
reconciliation this reading came out of is [R-348](348-three-devices-against-two-adapters.md).

## Trail

- 2026-09-08: **Not fired**, and the entry's account of the projection is corrected above. The
  container arm was re-run rather than reasoned about: `python:3.12-slim` with `/dev/dxg` and
  `/usr/lib/wsl` mounted, `pip install openvino` at 2026.3.1, `available_devices` reading `['CPU']`
  and `Core().get_property("NPU", "AVAILABLE_DEVICES")` reading `[]`, which is what the probe of
  2026-08-20 read and is the trigger's own command. The guest is unchanged as well: `/dev/dxg` is
  still the only device node, `/dev/accel` and `/dev/dri` do not exist, and the running kernel,
  6.6.114.1-microsoft-standard-WSL2, still reports `# CONFIG_DRM_ACCEL is not set` in
  `/proc/config.gz`. What is new is that `dxgkrnl` carries a third adapter the enumeration does not
  return, compute only, at host `00:0B.0`, with no dedicated video memory.
- 2026-09-06: **Not fired.** The trigger needs the device projected into the guest before any
  container can enumerate it, and the guest is unchanged from the probe above: `/dev/dxg` is still
  the only device node, `/dev/accel` and `/dev/dri` do not exist, and the running kernel,
  6.6.114.1-microsoft-standard-WSL2, still reports `# CONFIG_DRM_ACCEL is not set` in
  `/proc/config.gz`. With no accelerator node and no accel subsystem in the kernel there is nothing
  for `Core().get_property("NPU", "AVAILABLE_DEVICES")` to answer with, so the container arm was
  not rerun. (The projection reading of 2026-09-08 corrects the premise of this entry: the device
  is projected, and it is projected as a DXCore adapter rather than as a Linux accelerator node.)
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
- 2026-09-11: **Not fired.** The trigger's own command was run again: `python:3.12-slim` with
  `/dev/dxg` and `/usr/lib/wsl` mounted, `pip install openvino` resolving to 2026.3.1,
  `available_devices` reading `['CPU']` and `Core().get_property("NPU", "AVAILABLE_DEVICES")`
  reading `[]`, the same two answers as on 2026-08-20 and 2026-09-08. The guest is unchanged as
  well: `/dev/dxg` is still the only device node, `/dev/accel` and `/dev/dri` do not exist, and the
  running kernel, 6.6.114.1-microsoft-standard-WSL2, still reports `# CONFIG_DRM_ACCEL is not set`.
  The half of the condition that is outstanding is still the Linux user mode driver.
