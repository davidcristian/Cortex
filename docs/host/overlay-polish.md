# The overlay polish pass (tag W)

**The one item in this directory that is authoring, not validation.** Everything else here runs
code that already exists and writes down what happened. This writes code, in the ungated,
host-validated Tauri shell, and it can fail *review* rather than fail a check.

**Status: never attempted.** Tag **W**: only a real Win32 window shows whether transparency bleeds
and whether click-through margins behave.

## What it is, verbatim

Kept verbatim from [refinements/body-overlay.md](../refinements/body-overlay.md), the entry that
moved here:

> **Deferred overlay polish.** A proper transparent window + click-through margins (done
> together), the OS-window morph to a real screen corner, hide-on-blur, and a tighter CSP are
> detailed in [overlay-ux.md §4](../design/overlay-ux.md) and
> [body-overlay.md](../runbooks/body-overlay.md), recorded at ADR-0011 (2026-07-03 addendum). The
> design doc's smaller "later" marks (custom theme token sets, a licensed `@font-face`, a
> `Ctrl+K` command palette) ride along in §2-3 of the same doc.

and the design's own statement of why the four parts go together, from
[design/overlay-ux.md](../design/overlay-ux.md) section 4:

> The **OS-window-level** moves are deferred to a later overlay-polish pass, to be done together:
> a **transparent** window so only the panel floats over the desktop (a first pass bled through
> the panel and left a window border, so it waits to be done properly with **click-through** on
> the empty margins), morphing the window to a true *screen* corner (v1's orb sits at the window's
> own corner), and **hide-on-blur** (v1 toggles with the hotkey instead).

The terser form of the same list is [ADR-0011](../adr/ADR-0011-body-v1.md)'s 2026-07-03 addendum,
which is where the deferral was recorded at its origin (a planning doc carried a copy until it was
slimmed on 2026-07-19, so this and that addendum are now the two places it lives):

> **Deferred overlay polish (the Slice 8 conscious deferral), recorded at its origin ADR.** A
> proper transparent window + click-through margins (done together), the OS-window morph to a real
> screen corner, hide-on-blur, and a tighter CSP (null in v1) shipped deferred with the slice.

## Where v1 stands today

From [runbooks/body-overlay.md](../runbooks/body-overlay.md):

> **v1 window behaviour.** A fixed 640×720 frameless **opaque** always-on-top window; the hotkey
> **toggles** it (no hide-on-blur, so validation is predictable).

and:

> **CSP** is `null` for v1 (a fully local app loading only bundled assets); tighten it once the IPC
> + dev allow-list is settled on the host.

The opaqueness is deliberate, not an oversight: a transparent window makes every other Windows
check less predictable, so v1 chose predictability while the checks in
[windows-desktop.md](windows-desktop.md) were still owed. Doing them first and this second is the
right order.

## The four parts, and why they are one job

1. **A transparent window** so only the panel floats over the desktop.
2. **Click-through on the empty margins.** Inseparable from 1: a transparent window without it is
   an invisible rectangle that swallows clicks meant for whatever is behind it. The recorded
   history is that a first pass "bled through the panel and left a window border", which is what
   doing 1 without 2 looks like.
3. **The morph to a true screen corner.** Today's orb sits at the window's own corner because the
   window is fixed and centered. This is where the corner default from
   [design/overlay-ux.md](../design/overlay-ux.md) section 9 gets settled, which is why that open
   decision is folded in here rather than listed separately: it is not a decision until there is a
   real screen corner to put the orb in.
4. **A tighter CSP**, once the IPC and dev allow-list are settled on the host.

## What a good result looks like

- Only the panel is visible over the desktop; no window border, no rectangle of tint, no bleed
  through the panel's own background.
- Clicks on the empty margin reach the window behind, and clicks on the panel do not.
- The minimized orb sits in a real screen corner and the morph animation still plays.
- Hide-on-blur does not fight the hotkey toggle, and does not hide the window while a confirm card
  is open. That last one is a correctness constraint, not taste: a card that vanishes on blur is a
  gated action silently timing out.
- `just check` still passes. The overlay tree is gated at 100%, and the shell is fmt-checked in CI;
  the polish must not push logic out of the gated core into the ungated shell to get done.

## What a bad result looks like

The v1 attempt: a border, a bleed, and an unpredictable window. That is a real outcome, not a
hypothetical, and it is why this pass was deferred rather than half done.

## Record it

Update [design/overlay-ux.md](../design/overlay-ux.md) section 4 (which currently describes this
as deferred) and the v1-window note in
[runbooks/body-overlay.md](../runbooks/body-overlay.md), add a dated addendum to
[ADR-0011](../adr/ADR-0011-body-v1.md), and delete this doc and its row in [index.md](index.md).
If any part ships without another, say which and why, because "done together" is this entry's own
recorded finding.

## The one design decision still genuinely open

**A soft completion chime**, opt-in later or never
([design/overlay-ux.md](../design/overlay-ux.md) section 9). It is listed there among five open
design decisions, four of which are settled and stale in that doc: the palette is locked to one
gradient, both themes ship, the preview's auto-dismiss and hover-pause landed, and the corner is
part 3 above. The chime is untouched.
