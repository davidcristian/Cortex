# The hotkey hides the window without telling the overlay

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-06

The overlay's mode and the OS window's visibility are two states that nothing keeps in step.
`toggle_overlay` in `body/app/src-tauri/src/lib.rs` hides a visible window with `window.hide()`
and tells the webview nothing; it emits `cortex:activate` only when it shows the window. The
webview never hides the window either: an Escape, a dismiss or a preview's fade sets the mode to
`hidden` and leaves the opaque window on screen. The code is the same on both shells.

The Linux shell run of 2026-10-06 saw three effects
([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)):

- **A press during a turn** hides the window while the mode stays `panel`. A confirm card raised
  after it is never on screen, so the brain denies on its timeout with nobody having seen the
  question. [Overlay UX](../../design/overlay-ux.md) section 4 says a dismiss while streaming
  minimizes to the orb, and the host's polish item already calls a card that vanishes unseen a
  correctness constraint ([H-014](../../host/tasks/014-os-window-polish.md)).
- **The press that shows the window again** is no rising edge of the mode, so `useSummonEffect`
  runs nothing: no link probe, no chat list refresh and no reminder pull. With the brain stopped
  while the window was hidden, the dot stayed green for all 30 s of the capture after that summon.
- **After an Escape or a faded preview** the empty window stays on screen, and the next press hides
  it instead of summoning, so one press is lost.

**Do.** Make one of the two states follow the other. Either `toggle_overlay` asks the overlay to
dismiss (an event the webview turns into the `dismiss` action) and the overlay hides the window
when its mode reaches `hidden`, or the shell emits a hide event and the reducer treats it as a
dismiss. Either way the orb keeps the window shown during a turn. The reducer half is covered code
in `overlay/`; the shell half is one call in `lib.rs`. Check it on the Linux shell with the
runbook's Linux section: a press mid turn shows the orb, and a press after it summons with a probe.

## History

- 2026-10-06: filed by the Linux shell run of the Tauri commands, which met all three effects while
  driving [H-004](../../host/tasks/004-confirm-card-over-ipc.md) and
  [H-008](../../host/tasks/008-connection-indicator-ipc-hop.md).
