# An attached picture through real Tauri IPC

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md)

**What only this proves.** That a picture pasted from the Windows clipboard or dropped from
Explorer reaches the brain as the `ImageBlob` the overlay built. The overlay's paste and drop
handlers, the canvas reader and the refusal hand-back were run in headless Chromium against the
demo bridge on 2026-09-25, and the gRPC client's `ImageBlob` mapping is tested over a loopback
wire. Neither reaches WebView2's clipboard, its drag and drop, or the base64 `images` argument of
the shell's `converse` command.

**Do.** With the brain up and a vision-capable cortex, copy a screenshot (Win+Shift+S), paste it
into the composer with Ctrl+V, drop a JPEG from Explorer beside it, type a question and send it.
Then attach a file whose name ends `.png` but holds JPEG bytes, and send again.

**Pass.** Two thumbnails show, the reply describes both pictures, and a reopened chat shows the
brain's `(Attached to this message and not kept: ...)` note at the end of the question. The
mislabelled file comes back as the brain's `attachment_refused` sentence above the thumbnails, with
the question still in the field and both pictures still attached.

**Fail.** A paste that inserts nothing, or a drop that navigates the window to the file, is
WebView2 handling the event before the overlay does. A turn that reaches the brain with no
pictures is the IPC argument failing.

**Record it.** Edit [ADR-0070](../../adr/ADR-0070-user-attached-images.md) in place where it names
this as pending; then delete this section.

## History

- 2026-09-25: Filed when the overlay half of the attached-picture path was built, since only a
  Win32 desktop has the clipboard and the WebView2 drop target this needs.
