# The Linux shell attaches no pasted or dropped picture

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md) decision 5
**Verified:** 2026-10-06

Both ways in read a `File` from the webview: `clipboardData.files` on paste and
`dataTransfer.files` on drop (`body/app/src/components/Composer.tsx`). WebKitGTK 2.52.6, which
the Linux shell draws with, gives neither
([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)):

- a clipboard holding a picture, whether `xclip` under `image/png` or a GTK `set_image` with its
  full list of image targets, gives a `paste` event with no types and no files;
- a dragged file reaches the page's `drop` as a `text/uri-list` string and a `text/html` link,
  never as a `File`, and the page cannot read a `file://` address. This holds with Tauri's native
  drop handler off, which is how the overlay window ships
  ([readings](../../readings/tauri-ipc-commands.md#the-drop-guard)), so it is WebKitGTK's.

So on the Linux shell a picture cannot be attached at all, while the same overlay in Chromium and,
by ADR-0070's reading, in WebView2 gets a `File` for both.

**Design.** The shell reads bytes and never decodes them, so decision 5 stands: the webview's
canvas reader stays the one decoder.

1. **Paste.** A port in `body/crates/core/src/os.rs`, `ClipboardPicture`, whose one method returns
   the clipboard's picture as raw bytes and a media type, or none, with a fake and a contract test.
   The Linux adapter in `os_linux` converts the X11 `CLIPBOARD` selection to the first of
   `image/png`, `image/jpeg` and `image/webp` its owner offers, through the pure Rust `x11rb`
   client the crate already uses (with `INCR` for a large picture), so no system library joins
   `check-body`; it refuses anything over a byte cap. The Windows adapter returns none unless
   [H-024](../../host/tasks/024-attached-picture-over-ipc.md) shows WebView2 gives the page no
   `File` for a pasted screenshot; macOS is a stub.
2. A shell command, `clipboard_picture`, returns that as base64, as `converse` takes `images`. In
   the overlay, a `HostClipboard` port with a Tauri adapter and an adapter that returns nothing for
   the browser build; `onPaste` calls it only for a paste with no files and no `text/plain`, and
   hands the bytes to `onAttach` as a `Blob` of that type.
3. **Drop.** `tauri.conf.json` keeps `dragDropEnabled` false, which WebView2 needs. A
   `tauri.linux.conf.json`, which Tauri merges over it on Linux only, sets it true, so the native
   handler takes a Linux drop before WebKit does. The shell keeps the paths of the last
   `WindowEvent::DragDrop` drop, and a `dropped_pictures` command reads those paths and no other,
   skipping any that is not a local file: a command that read a path the page names would give
   page script every local file. The overlay listens with `onDragDropEvent` from
   `@tauri-apps/api/webview`, takes a drop whose position is over the composer, and hands the
   bytes to `onAttach`.
4. `dropGuard.test.ts` reads both config files, and `scripts/ci_paths.py` routes the Linux file
   as it routes `tauri.conf.json`. Record the shell's byte reads in ADR-0070 decision 5.
5. Check it on the Linux shell with the runbook's Linux section: an `xclip` PNG pasted with Ctrl+V
   and a file dragged from the drag source each show a thumbnail, and a link dragged over the
   window changes nothing.

## History

- 2026-10-06: filed by the Linux shell run of the attached-picture path, which met both gaps
  before it reached the IPC hop and drove the rest with a paste built in the page. A second run,
  with the native drop handler off, showed the drop gap is WebKitGTK's.
