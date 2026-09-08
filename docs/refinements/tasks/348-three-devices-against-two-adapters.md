# Three projected devices against two enumerated adapters, unreconciled

**Status:** landed 2026-09-08
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

Opened 2026-08-20 by a review of the NPU probe recorded at the origin decision. That record makes
two measurements of the same paravirtualized surface and never puts them side by side. The guest's
PCI bus carries **three** Microsoft vPCI devices of display class `0x030200`, `1414:008e` twice and
`1414:008a`, every one bound to `dxgkrnl`. The adapter channel those devices are reached through
enumerates **two** adapters under every capability attribute, the discrete GPU and the integrated
one. Three devices, two adapters, and nothing said about the third.

**Reconciled 2026-09-08, and the answer is not the one this entry guessed.** The reading is
`D3DKMTEnumAdapters2`, which `/usr/lib/wsl/lib/libdxcore.so` exports, called three ways in one
process. Asked for a count with a null buffer it answers **3**. Given room for one or two adapters
it refuses with `STATUS_BUFFER_TOO_SMALL` (`0xc0000023`), so three is a requirement rather than an
estimate. Given room for three it succeeds and fills **2**, rewriting the count to 2. The sequence
reproduced identically on three consecutive runs. So the third device is not a device that carries
no adapter: three adapters exist and the enumeration returns two of them.

The one it leaves out is identifiable, and it answers every query the other two answer. Beside the
three vPCI devices, `dxgkrnl` owns three VMBus channels of class
`{6e382d18-3336-4f4b-acc4-2b7703d4df4a}` whose instance GUIDs begin `0031d90a`, `0031ddff` and
`0031eb6d`, and each of those hex prefixes is one adapter LUID. The enumeration returns `0x31D90A`
and `0x31DDFF`; `0x31EB6D` is the one it omits. `D3DKMTOpenAdapterFromLuid` opens all three. The
control that makes an open evidence rather than a handle the library hands out for anything: the
neighbouring values `0x31EB6C` and `0x31EB6E`, zero, and an arbitrary LUID are each refused with
`STATUS_INVALID_PARAMETER`.

Read through `D3DKMTQueryAdapterInfo` on a handle opened that way, the three adapters are:

| adapter LUID | host PCI address | dedicated video memory | `D3DKMT_ADAPTERTYPE` |
| --- | --- | --- | --- |
| `0x31D90A` | `01:00.0` | 23.57 GiB | `0x2091`: render, hybrid discrete, paravirtualized |
| `0x31DDFF` | `00:02.0` | 32 GiB | `0x20A1`: render, hybrid integrated, paravirtualized |
| `0x31EB6D` | `00:0B.0` | none | `0x2881`: render, **compute only**, paravirtualized |

**It cost the conclusion more than this entry said.** The paragraph above argued that the
discrepancy is free, because "a third device that enumerates as no adapter at all cannot be one
that" answers to the compute accelerator type. The third device does carry an adapter, and that
adapter sets `ComputeOnly`, which is bit 11 of `D3DKMT_ADAPTERTYPE`. So the argument does not hold.
What the NPU probe's conclusion rests on instead is measured elsewhere and unaffected: the guest has
no `/dev/accel` and a kernel built `# CONFIG_DRM_ACCEL is not set`, OpenVINO in a container
enumerates nothing under `NPU`, and Intel's NPU driver packages ship no Linux user mode library.
What the type reading adds is that the device the probe was looking for is projected after all,
which moves the blocker rather than removing it and is written up at the origin decision and in
[R-192](192-intel-npu-placement-target.md).

**Which of the three vPCI devices it is, read off the offer order.** The VMBus channel ids
interleave: channel 6 is the vPCI device on bus `d1e4` (`1414:008e`) and channel 7 its vGPU channel
`0x31D90A`; channel 8 is `dxgkrnl`'s global channel; channel 9 is the vPCI device on bus `cd99`
(`1414:008e`) and channel 10 its vGPU channel `0x31DDFF`; channel 11 is the vPCI device on bus
`2c5d` (`1414:008a`) and channel 12 its vGPU channel `0x31EB6D`. Each display-class device is
offered immediately before one vGPU channel, so the pairing is read off that adjacency rather than
off a link sysfs carries, and on that reading the odd device is `1414:008a`. This entry's guess
named the same device and the wrong reason for it: the candidate it proposed was the compositor or
indirect display path, and neither enumerated adapter carries the `IndirectDisplayDevice` bit while
the third is a compute accelerator.

## Trail

- 2026-09-08: reconciled and closed. Three adapters exist where two enumerate, the third opens by
  LUID and reports itself compute only at host `00:0B.0` with no dedicated video memory, and the
  device it belongs to is `1414:008a` by the VMBus offer order. Recorded in the ADR-0012 addendum of
  the same day, which is the sentence this entry asked the origin decision for.
- 2026-08-20: opened by a review of the NPU probe, which found the guest's device count and the
  adapter count differing by one with no sentence joining them.
