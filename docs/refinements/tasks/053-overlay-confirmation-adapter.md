# Real overlay confirmation adapter

**Status:** done 2026-07-08
**Area:** untrusted-content
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

`RpcConfirmer` sends the confirmation exchange over the `Converse` stream to the overlay's
approval card. The confirmation table was revised in the same change: an untainted call that needs
approval asks for it, and a tainted one is denied outright, per ADR-0013 decision 4. The
Windows-native validation of the card moved to
[docs/host/windows-desktop.md](../../host/index.md#windows-desktop) on 2026-07-19 and is no longer
counted here.

## History

- 2026-07-08: `RpcConfirmer` shipped, sending the confirmation exchange over the `Converse`
  stream to the overlay's approval card, with the confirmation table revised in the same change.
- 2026-07-19: The Windows-native validation of the card moved to
  [docs/host/windows-desktop.md](../../host/index.md#windows-desktop).
