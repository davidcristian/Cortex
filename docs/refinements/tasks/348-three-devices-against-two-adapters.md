# Three projected devices against two enumerated adapters, unreconciled

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Trigger:** the next run of the NPU probe, meaning anybody asking again what this guest is given,
whether after a WSL upgrade or against a different machine.

Opened 2026-08-20 by a review of the NPU probe recorded at the origin decision. That record makes
two measurements of the same paravirtualized surface and never puts them side by side. The guest's
PCI bus carries **three** Microsoft vPCI devices of display class `0x030200`, `1414:008e` twice and
`1414:008a`, every one bound to `dxgkrnl`. The adapter channel those devices are reached through
enumerates **two** adapters under every capability attribute, the discrete GPU and the integrated
one. Three devices, two adapters, and nothing said about the third.

**It costs the conclusion nothing.** The finding is that no adapter answers to the compute
accelerator or the NPU hardware type, and a third device that enumerates as no adapter at all cannot
be one that does. The reason to record it is that a reader re-running the probe hits the discrepancy
in the first two commands and has no note saying it was seen. An unexplained count is the kind of
loose end that gets re-derived from scratch, or worse, read as evidence of a hidden device.

**The likely answer, which is a guess and is marked as one.** WSL projects a device per host adapter
plus at least one that is not an adapter, the usual candidate being the compositor or indirect
display path, and `1414:008a` differing in device id from the pair suggests it is the odd one rather
than a duplicate. Nothing here measured that, and the guess is written down so the next probe can
confirm or drop it rather than start over.

**What would close it.** One command per device, reading `dxgkrnl`'s view of each vPCI device and
saying which of the three carries no adapter, and one sentence at the origin decision reconciling
the counts. It is a probe, not a change, and it belongs with whatever re-runs the rest.

## Trail

- 2026-08-20: opened by a review of the NPU probe, which found the guest's device count and the
  adapter count differing by one with no sentence joining them.
