# The reserved rail is unmeasured on WebKitGTK

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22
**Verified:** 2026-10-04

Every scroll container in `body/app/src/overlay.css` reserves its scrollbar with
`scrollbar-gutter: stable` and subtracts that band from its inline-end padding, on the assumption
that the band is `--rail`, the 6px that `.stage ::-webkit-scrollbar` sets.
[146](146-reserved-rail-assumed-width.md) lists the seven containers. The assumption was measured
on Chromium only, where `.history` and `.field` reserve exactly 6px. The shell now runs on Linux,
where Tauri renders through WebKitGTK ([751](751-the-shell-has-never-been-linked-or-run-on-linux.md)),
and nobody has read what WebKit reserves for a styled `::-webkit-scrollbar` under
`scrollbar-gutter: stable`. [ADR-0035](../../adr/ADR-0035-console-and-motion.md) says the same:
WebKit's gutter is unmeasured.

The reading: open the overlay from the Vite dev server in WebKitGTK, either in the Linux shell as
the [overlay runbook](../../runbooks/body-overlay.md) runs it or in any WebKitGTK view of the same
page, and read `offsetWidth - clientWidth` less the two border widths on `.history`, `.field` and
`.reminders`, once with each one overflowing and once without. The userspace prefix the runbook
links against is not on this host now; the [shell clippy readings](../../readings/shell-clippy.md)
give the recipe that builds it, and it holds `libwebkit2gtk-4.1`.

What it decides: 6px on all three in both states means the arithmetic balances on the Linux shell,
and this closes with the figures in a readings record and ADR-0035's sentence updated. Any other
width means the padding is wrong on an engine the body runs on, and the measured-width remedy in
146 is due for WebKit as well as for an engine without `::-webkit-scrollbar`.

## History

- 2026-10-04: Filed from a review of [146](146-reserved-rail-assumed-width.md), once the Linux
  shell had run under WebKitGTK and the gutter it reserves had become a reading this host can take.
