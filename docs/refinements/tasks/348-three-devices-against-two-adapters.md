# Three display devices in the guest against two enumerated adapters

**Status:** done 2026-09-08
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The NPU probe recorded at the origin decision makes two measurements of the same paravirtualized
surface and never puts them side by side. The guest's PCI bus has three Microsoft vPCI devices of
display class `0x030200`, `1414:008e` twice and `1414:008a`, every one bound to `dxgkrnl`. The
adapter channel those devices are reached through enumerates two adapters under every capability
attribute, the discrete GPU and the integrated one. Nothing explained the third.

Reconciled 2026-09-08, and the answer is not the one this entry guessed. The reading is
`D3DKMTEnumAdapters2`, which `/usr/lib/wsl/lib/libdxcore.so` exports, called three ways in one
process. Asked for a count with a null buffer it answers 3. Given room for one or two adapters it
refuses with `STATUS_BUFFER_TOO_SMALL` (`0xc0000023`), so three is a requirement rather than an
estimate. Given room for three it succeeds and fills 2, rewriting the count to 2. The sequence
reproduced identically on three consecutive runs. So three adapters exist and the enumeration
returns two of them.

The one it leaves out is identifiable. Beside the three vPCI devices, `dxgkrnl` owns three VMBus
channels of class `{6e382d18-3336-4f4b-acc4-2b7703d4df4a}` whose instance GUIDs begin `0031d90a`,
`0031ddff` and `0031eb6d`, and each of those hex prefixes is one adapter LUID. The enumeration
returns `0x31D90A` and `0x31DDFF`; `0x31EB6D` is the one it omits. `D3DKMTOpenAdapterFromLuid`
opens all three, and the neighbouring values `0x31EB6C` and `0x31EB6E`, zero, and an arbitrary LUID
are each refused with `STATUS_INVALID_PARAMETER`, which makes an open evidence rather than a handle
the library hands out for anything.

Read through `D3DKMTQueryAdapterInfo` on a handle opened that way, the three adapters are:

| adapter LUID | host PCI address | dedicated video memory | `D3DKMT_ADAPTERTYPE` |
| --- | --- | --- | --- |
| `0x31D90A` | `01:00.0` | 23.57 GiB | `0x2091`: render, hybrid discrete, paravirtualized |
| `0x31DDFF` | `00:02.0` | 32 GiB | `0x20A1`: render, hybrid integrated, paravirtualized |
| `0x31EB6D` | `00:0B.0` | none | `0x2881`: render, compute only, paravirtualized |

That cost the original conclusion. It argued the difference was free, because a third device that
enumerates as no adapter cannot be the compute accelerator. The third device does have an adapter,
and that adapter sets `ComputeOnly`, bit 11 of `D3DKMT_ADAPTERTYPE`. What the NPU probe's
conclusion rests on instead is measured elsewhere and unaffected: the guest has no `/dev/accel` and
a kernel built `# CONFIG_DRM_ACCEL is not set`, OpenVINO in a container enumerates nothing under
`NPU`, and Intel's NPU driver packages ship no Linux user mode library. What the type reading adds
is that the device the probe was looking for is projected after all, which moves the blocker rather
than removing it ([R-192](192-intel-npu-placement-target.md)).

Which of the three vPCI devices it is comes off the offer order. The VMBus channel ids interleave:
channel 6 is the vPCI device on bus `d1e4` (`1414:008e`) and channel 7 its vGPU channel `0x31D90A`;
channel 8 is `dxgkrnl`'s global channel; channel 9 is the vPCI device on bus `cd99` (`1414:008e`)
and channel 10 its vGPU channel `0x31DDFF`; channel 11 is the vPCI device on bus `2c5d`
(`1414:008a`) and channel 12 its vGPU channel `0x31EB6D`. Each display-class device is offered
immediately before one vGPU channel, so the pairing comes from that order, and the odd device is
`1414:008a`.

## History

- 2026-08-20: Opened by a review of the NPU probe, which found the guest's device count and the
  adapter count differing by one with no sentence joining them.
- 2026-09-08: Reconciled and closed. Three adapters exist where two enumerate, the third opens by
  LUID and reports itself compute only at host `00:0B.0` with no dedicated video memory, and the
  device it belongs to is `1414:008a` by the VMBus offer order. Recorded the same day in the
  readings ADR-0012 cites
  ([subagent budget](../../readings/subagent-budget.md#the-npu-from-a-container)).
