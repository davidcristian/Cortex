# An attached picture through real Tauri IPC

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md)
**Verified:** 2026-10-07

Narrowed 2026-10-06 to the two ways in that WebView2 owns. On the Linux shell, pictures handed to
the composer's paste handler went through the canvas reader, the base64 `images` argument of the
shell's `converse` command and the shell's decode into the brain: two thumbnails showed, the reply
described both, a reopened chat showed the brain's `(Attached to this message and not kept: ...)`
note, and a brain that could not see refused the turn with the question and both pictures handed
back ([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)). That
path has no Windows code. The same run showed that a file named `.png` holding JPEG bytes is
attached and accepted, not refused: the canvas encodes it again as PNG before it is sent.

**What only this proves.** That WebView2 hands the composer a `File` for a picture pasted from the
Windows clipboard and for one dropped from Explorer. WebKitGTK gives neither, so the Linux shell
reads both itself ([readings](../../readings/tauri-ipc-commands.md#a-drop-through-the-shell)).
Outside Linux the overlay window sets `dragDropEnabled` to false, which by wry 0.55's source leaves
WebView2's own external drop on, so an Explorer drop should reach the composer as a `File`; that
is read from the source and not run.

**Do.** With the brain up and a vision-capable cortex, copy a screenshot (Win+Shift+S), paste it
into the composer with Ctrl+V, drop a JPEG from Explorer beside it, type a question and send it.
Then drag a link from a browser over the window and let go.

**Pass.** Two thumbnails show and the reply describes both pictures. The dragged link changes
nothing: the window stays on the overlay.

**Fail.** A paste that inserts nothing is WebView2 offering the screenshot in a format it does not
give the page as a file. A drop that does nothing is WebView2 refusing an external drop with Tauri's
handler off. A drop that navigates the window to the file or the link is a drag whose types the
window's drop guard (`body/app/src/overlay/dropGuard.ts`) does not cancel.

**Record it.** Edit [ADR-0070](../../adr/ADR-0070-user-attached-images.md) in place where it names
this as pending; then delete this section.

## History

- 2026-09-25: Filed when the overlay half of the attached-picture path was built, since only a
  Win32 desktop has the clipboard and the WebView2 drop target this needs.
- 2026-10-06: narrowed after the Linux shell run sent pictures through the real IPC hop into the
  brain. The overlay window's native drop handler was turned off the same night, so the drop half
  now checks that change on WebView2.
