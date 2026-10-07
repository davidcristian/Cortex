# A soft completion chime

**Status:** never attempted
**Session:** overlay-polish
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-07

A soft completion chime, opt-in later or never
([design/overlay-ux.md](../../design/overlay-ux.md) section 9). That section now holds two lines:
this one, still open, and the corner, which is part 3 of the overlay polish pass. What blocks the
chime is the user's decision, not hardware. Once it is decided, the overlay code is portable and
reachable anywhere; only hearing it through WebView2 needs the Windows desktop.

## History

- 2026-07-12: with this user pass and the one of 2026-07-03, every other line of
  [design/overlay-ux.md](../../design/overlay-ux.md) section 9 was settled, which leaves the chime
  as the last open line there.
- 2026-07-19: when host work was moved into its own backlog, the chime was recorded among the
  decisions awaiting the user, which are weighed rather than run. Those decisions are listed as
  pointers rather than copied, so that a decision has exactly one home. The pointer for the chime
  is [design/overlay-ux.md](../../design/overlay-ux.md) section 9.
- 2026-10-07: corrected. The design doc no longer lists the four settled decisions this file
  called stale there, and the file now says the block is the user's decision rather than a Win32
  desktop.
