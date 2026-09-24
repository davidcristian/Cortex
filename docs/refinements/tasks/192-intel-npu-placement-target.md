# The Intel NPU as a third placement target

**Status:** open, waiting for its trigger
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** An NPU device enumerating from inside a container, meaning
`Core().get_property("NPU", "AVAILABLE_DEVICES")` returns anything at all. That is one container
run: `pip install openvino` over `python:3.12-slim`, with `/dev/dxg` and `/usr/lib/wsl` handed in,
then read `available_devices` and that property. This entry's history records what the run returned
when it was last taken, and the body records which half of the condition is already met.
**Verified:** 2026-09-24

An OpenVINO `InferenceBackend` adapter plus a `PlacementTarget.NPU` would use the otherwise-idle NPU
for tiny subagents or embeddings, which serves the same goal as the container limits above.
OpenVINO GenAI is the engine, because llama.cpp has no NPU path. The hardware is present (an Intel
Core Ultra 9 275HX, confirmed 2026-07-01), so two questions decide it: whether the NPU is reachable
from the dockerized WSL2 brain at all, and whether NPU inference for a 2-4B model is fast and mature
enough to be worth a target.

The first question is answered and the answer is no, for now. Measured at the guest: the only device
node is `/dev/dxg`, `/dev/accel` and `/dev/dri` do not exist, the PCI bus has no Intel silicon, and
the kernel is built `# CONFIG_DRM_ACCEL is not set`, so `intel_vpu` could not bind a device it was
handed. Measured from a container: OpenVINO's NPU plugin ships in the wheel and loads, and it
enumerates nothing. Not measured: whether the machine has an NPU at all, since this guest cannot see
Windows device state.

Of the 1,103 Windows driver packages WSL maps in, exactly five ship Linux user-mode libraries, the
Intel graphics package in its two staged versions and the NVIDIA one in its three, while both NPU
packages ship only Windows DLLs. So the condition that revives this work has two halves, WSL
projecting the device and the vendor shipping a Linux driver for it.

The projection half is already met. `D3DKMTEnumAdapters2` asked for a count returns three where the
list it fills has two, a buffer sized for fewer than three is refused, and the adapter the list
omits opens by LUID and describes itself: host PCI address `00:0B.0`, no dedicated video memory, and
an adapter type of `0x2881`, whose set bits are render, paravirtualized and compute only. `00:0B.0`
is where Intel's NPU sits on this CPU generation, and the driver store's `npu.inf` of class
`ComputeAccelerator` covers the Arrow Lake id, so calling that adapter the NPU is an inference from
the address, the type and those packages rather than a reading of Windows device state. What is
missing is the Linux user-mode driver. The count reconciliation this came out of is
[R-348](348-three-devices-against-two-adapters.md).

The second question is untouched, there being nothing to measure it on.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section.
- 2026-07-19: The two questions and the hardware confirmation moved here from the roadmap's Slice
  8.5 block, where they were the only record of either.
- 2026-07-19: It stayed in this backlog rather than moving to [docs/host/](../../host/index.md),
  because the work itself is code even where only the host's hardware can judge the result.
- 2026-08-20: Probed, and the trigger changed rather than the entry closing. The blocker is
  confirmed at the guest and at the container, so the trigger moves from a feasibility pass to the
  state of the world that would make rerunning it worthwhile.
- 2026-08-20: Three counts corrected against the driver store. The denominator is 1,038 package
  directories, not the 1,349 entries `ls` reports, the rest being 311 `.ini` sidecars; the Intel
  graphics package is counted in its two staged versions; and the NPU package is staged twice too.
- 2026-09-06: Not fired. The guest is unchanged from the probe above, so the container run was not
  repeated.
- 2026-09-08: Not fired, and the account of the projection is corrected above. The container run was
  repeated: `pip install openvino` at 2026.3.1, `available_devices` reading `['CPU']` and
  `Core().get_property("NPU", "AVAILABLE_DEVICES")` reading `[]`. What is new is the third adapter
  `dxgkrnl` has that the enumeration does not return.
- 2026-09-11: Not fired. The trigger's command was run again with the same two answers, and the
  guest is unchanged.
- 2026-09-17: Not fired. `pip install openvino` now resolves to 2026.4.0, a newer release than the
  2026.3.1 the two runs before it installed, and the answers did not move with it. The guest is
  unchanged: `/dev/dxg` is still the only device node and the running kernel,
  6.6.114.1-microsoft-standard-WSL2, still reports `# CONFIG_DRM_ACCEL is not set`.
- 2026-09-24: Not fired, read from the guest only: Docker was left to a detached GPU run, so the
  container run was not repeated. The guest is unchanged, and `npu.inf` and `npu_extension.inf`
  still hold no `.so` file, which is the vendor half. The driver store now holds 1,103 package
  directories beside 376 `.ini` sidecars, and a third staged NVIDIA version makes five packages
  with Linux libraries; the count above is corrected to that.
