# Real overlay confirmation adapter

**Status:** landed 2026-07-08
**Area:** untrusted-content
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

The `SeamConfirmer` threads the confirm
exchange over the `Converse` stream to the overlay's approval card; the gate table was revised
in the same slice (untainted gated → confirm; tainted gated → denied outright, per the
ADR-0013 2026-07-08 addendum). Only the Windows-native validation of the card remains
host-side, and it **moved to [docs/host/windows-desktop.md](../../host/index.md#windows-desktop) on
2026-07-19** with that sentence kept verbatim, so it is no longer counted here.

## Trail

- 2026-07-08: The `SeamConfirmer` landed with Slice 8.8, threading the confirm exchange over
  the `Converse` stream to the overlay's approval card, and the gate table was revised in the
  same slice.
- 2026-07-19: The Windows-native validation of the card left for
  [docs/host/windows-desktop.md](../../host/index.md#windows-desktop) with the host-side extraction,
  which took this area's count from 13 to 11 together with the ~31B harness run.
