# The reserved rail is 6px only on one engine

**Status:** open, waiting for a consumer
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22, scrollbars as reserved chrome ([overlay-ux.md §2](../../design/overlay-ux.md))
**Trigger:** The overlay running on an engine without `::-webkit-scrollbar`, such as Gecko, since only such an engine takes the fenced branch.
**Verified:** 2026-10-04

Every scroll container sets `scrollbar-gutter: stable` and pays for the rail out of its own
inline-end padding, either subtracted from a padding big enough to hold it
(`calc(16px - var(--rail))` on `.history` and `.rows`, the whole 6px inset on `.switcher` and
`.reminders`) or added beside a padding that had none (`.thoughts-body`, `.confirm-draft`,
`.field`). Every one of those numbers assumes the reserved rail really is `--rail`. That is true
in Chromium, true in WebKitGTK only while a box overflows
([784](784-a-fitting-box-reserves-the-wrong-rail-on-webkitgtk.md)), and false on an engine without
`::-webkit-scrollbar`, which is the case this task is about.

Chromium honours the standards properties over the pseudo-elements when both are set, so leaving
them both unfenced would reserve a band the padding never accounted for: measured 2026-07-20 on
`.switcher`, the shipped fence gives a computed `scrollbar-width: auto` and a 6px gutter, while
adding `scrollbar-width: thin` alone takes the gutter to 10px and 4px off the content width. The
standards path is therefore behind `@supports not selector(::-webkit-scrollbar)`, where `thin` is
whatever the browser says it is. On such an engine the subtraction does not balance and the
inline-end margin reads a few px wider than the other side. What matters survives, since nothing
moves when the bar appears, because the gutter is reserved either way; what is lost is exact
symmetry on an engine the body does not run on.

The fix, whenever one of them becomes a target, is to measure the width rather than assume it: a
probe element read once at startup (`offsetWidth - clientWidth`) published as a second custom
property. It cannot be published as `--rail`, because `::-webkit-scrollbar { width: var(--rail) }`
would then consume its own output. That makes it a change to every subtraction in the stylesheet
rather than a line of wiring, which is why it is not a CSS-only change. The probe module
(`overlay/measured.ts`) exists already. Whoever takes it should also take the borders off the
reading first: `.reminders` answers 8px for a 6px rail inside two 1px edges.

## History

- 2026-07-20: Measured on `.switcher` and filed when scrollbars became reserved chrome.
- 2026-08-03: Re-read against the tree and against the browser when the chat floor's probe was
  built, and it stays rather than using `overlay/measured.ts`. On the engine that ships, the
  measurement is circular. `.history` and `.field` were confirmed at exactly 6px, and the recipe
  holds only on a box with no border.
- 2026-09-13: Checked again; the premise is unchanged and only the pointers into the stylesheet
  moved. All six funding shapes are still there. The trigger has not fired: the overlay runs on
  WebView2 alone, so nothing reaches the fenced branch.
- 2026-09-19: Checked again; the premise holds and the trigger has not fired, the Windows shell
  still being WebView2. Every stylesheet citation from 2026-09-13 after line 300 was one line
  short from the day it was written, because the same commit added a line to the edge comment
  above them. The funding shapes sit at `body/app/src/overlay.css` lines 820 (`.history`), 1718
  (`.rows`), 1143 (`.thoughts-body`), 1305 (`.confirm-draft`) and 1512 (`.field`), `--rail: 6px`
  is at line 40, the pseudo-element width that sets it at lines 146 to 148, and the standards
  fence runs from line 202 to 207. The trigger used to name any engine that is not Chromium, which
  is wider than the case it guards: `@supports not selector(::-webkit-scrollbar)` is false
  wherever the pseudo-element exists, and WebKit, the engine a Tauri shell uses on Linux and
  macOS, is where it came from. So only an engine without it, Gecko being the one in use, reaches
  the unbalanced subtraction. Whether WebKit's gutter reserves exactly `--rail` under
  `scrollbar-gutter: stable` has not been measured. The stylesheet's own comment on this trade
  still named the rejected recipe and gave ADR-0011 as the origin; it now names the second
  property and ADR-0035.
- 2026-09-30: Checked again; the premise holds and the trigger has not fired. The shell now has
  a Linux `start`, where Tauri renders through WebKitGTK, an engine with `::-webkit-scrollbar`, so
  nothing reaches the fenced branch there either; that shell has never been run
  ([751](751-the-shell-has-never-been-linked-or-run-on-linux.md)). The stylesheet is shorter and
  every pointer moved: `--rail` is at line 19 of `body/app/src/overlay.css`, the pseudo-element
  width at lines 60 to 63, the fence at 98 to 103, and the funding shapes at 537 (`.history`), 759
  (`.thoughts-body`), 902 (`.confirm-draft`), 1026 (`.field`), 1203 (`.rows`), 1659 (`.switcher`)
  and 1915 (`.reminders`, still inside a 1px border).
- 2026-10-04: Checked again; the premise holds, the stylesheet has not changed since 2026-09-25,
  so every pointer above is still right, and the trigger has not fired. The Linux shell has now run
  ([751](751-the-shell-has-never-been-linked-or-run-on-linux.md), closed 2026-10-01) and painted
  the overlay through WebKitGTK 2.52.6, which has `::-webkit-scrollbar` and so does not reach the
  fenced branch. The band it reserves under `scrollbar-gutter: stable` was then read with the
  overlay's stylesheet ([scrollbar-gutter readings](../../readings/scrollbar-gutter.md)): 6px while
  a box overflows, and the GTK theme's band while it fits. The subtraction therefore does not
  balance on the Linux shell either, through a different path with a different fix, filed as
  [784](784-a-fitting-box-reserves-the-wrong-rail-on-webkitgtk.md). The measured-width probe here
  cannot fix that one, since the band changes with the box's state.
