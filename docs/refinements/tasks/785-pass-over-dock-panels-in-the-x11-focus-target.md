# Pass over dock panels in the X11 focus target

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-04

The X11 window target in `os_linux/src/focus.rs` takes the topmost viewable top-level window that is
not `InputOnly` or override-redirect, has a non-empty `WM_NAME` on it or under it, and holds no
window of the body. A desktop panel passes every one of those tests: it is a managed, titled
window, and the EWMH stacking order puts docks above normal windows, so on such a desktop a window
capture would point at the panel.

The fix reads `_NET_WM_WINDOW_TYPE` (an `ATOM` list) of each window in the tree read and passes
over a top-level window whose client lists `_NET_WM_WINDOW_TYPE_DOCK` or
`_NET_WM_WINDOW_TYPE_DESKTOP`. The type atoms are interned once per grab, the choice stays in
`focus` over a new `TreeWindow` field, and the fake X server test scripts the new request. It can be
checked here on `Xvfb` with no window manager, by setting the property on a test window.

## History

- 2026-10-04: Filed when the X11 window target was built under
  [263](263-linux-and-macos-capture-backends.md).
