# The OS-window half of the overlay polish

**Status:** never attempted
**Session:** overlay-polish
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

**The one item in this directory that is authoring, not validation.** Everything else here runs
code that already exists and writes down what happened. This writes code, in the Tauri shell that
is validated on the host rather than in CI, and it can fail *review* rather than fail a check. Only
a real Win32 window shows whether transparency bleeds and whether click-through margins behave.

## What it is

Four OS-window changes deferred together and recorded at
[ADR-0011](../../adr/ADR-0011-body-v1.md)'s host-only consequence and in
[design/overlay-ux.md](../../design/overlay-ux.md) section 4: a transparent window so only the panel
floats over the desktop, click-through on the empty margins, the morph to a true screen corner, and
a tighter CSP (`null` in v1). The design doc's smaller "later" marks, custom theme token sets, a
licensed `@font-face` and a `Ctrl+K` command palette, come with them in sections 2 and 3 of that
doc.

Today v1 is a fixed 640x720 frameless **opaque** always-on-top window that the hotkey toggles, with
no hide-on-blur so validation is predictable, and CSP `null` for a fully local app loading only
bundled assets. The opaqueness is deliberate: a transparent window makes every other Windows check
less predictable, so v1 chose predictability while the checks in
[windows-desktop.md](../index.md#windows-desktop) were still owed. Doing them first and this second
is the right order.

## The four parts, and why they are one job

1. **A transparent window** so only the panel floats over the desktop.
2. **Click-through on the empty margins.** Inseparable from 1: a transparent window without it is an
   invisible rectangle that takes clicks meant for whatever is behind it. A first pass bled through
   the panel and left a window border, which is what doing 1 without 2 looks like.
3. **The morph to a true screen corner.** Today's orb sits at the window's own corner because the
   window is fixed and centered. This is where the corner default from
   [design/overlay-ux.md](../../design/overlay-ux.md) section 9 gets settled, which is why that open
   decision is folded in here: it is not a decision until there is a real screen corner to put the
   orb in.
4. **A tighter CSP**, once the IPC and dev allow-list are settled on the host.

## What a good result looks like

- Only the panel is visible over the desktop; no window border, no rectangle of tint, no bleed
  through the panel's own background.
- Clicks on the empty margin reach the window behind, and clicks on the panel do not.
- The minimized orb sits in a real screen corner and the morph animation still plays.
- Hide-on-blur does not fight the hotkey toggle, and does not hide the window while a confirm card
  is open. That last one is a correctness constraint rather than taste: a card that vanishes on blur
  is an action awaiting approval timing out where nobody sees it.
- `just check` still passes. The overlay tree is covered at 100% and the shell is fmt-checked in CI;
  the polish must not push logic out of the covered core into the shell to get done.

## What a bad result looks like

The v1 attempt: a border, a bleed, and an unpredictable window. That is a real outcome rather than a
hypothetical, and it is why this pass was deferred rather than half done.

## Record it

Update [design/overlay-ux.md](../../design/overlay-ux.md) section 4 and the v1-window note in
[runbooks/body-overlay.md](../../runbooks/body-overlay.md), edit
[ADR-0011](../../adr/ADR-0011-body-v1.md) in place where the pass changes what it states, and delete
this doc and its row in [index.md](../index.md). If any part ships without another, say which and
why, because "done together" is this entry's own recorded finding.

## History

- 2026-07-19: moved out of the refinements backlog, where it had been an entry in the body and
  overlay area, and filed as host work, with a dated pointer left at the origin. Of everything that
  backlog held, this was the only entry that is authoring rather than deferred design anyone can
  pick up. The old index described it in two ways, as that area's host-side validation item and as
  the only authoring entry; this file says authoring.
- 2026-07-19: the reason for moving it rather than leaving it there under a tag is that the
  refinements backlog holds work anyone can pick up and its emptiness is part of the README's
  finish line, which would then have waited on the maintainer writing Rust.
- 2026-07-19: filed as a work session rather than a validation session, blocked on nothing, and
  named the one piece of host work that is not urgent for correctness.
