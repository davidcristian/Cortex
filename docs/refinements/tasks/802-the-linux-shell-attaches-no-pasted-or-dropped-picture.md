# The Linux shell attaches no pasted or dropped picture

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md) decision 5
**Verified:** 2026-10-06

Both ways in read a `File` from the webview: `clipboardData.files` on paste and
`dataTransfer.files` on drop (`body/app/src/components/Composer.tsx`). WebKitGTK 2.52.6, which
the Linux shell draws with, gives neither
([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)). A paste
now reads the X clipboard through the shell's `clipboard_picture` command instead
([readings](../../readings/tauri-ipc-commands.md#a-paste-through-the-shell)). A drop still
attaches nothing: a dragged file reaches the page's `drop` as a `text/uri-list` string and a
`text/html` link, never as a `File`, and the page cannot read a `file://` address. This holds with
Tauri's native drop handler off, which is how the overlay window ships
([readings](../../readings/tauri-ipc-commands.md#the-drop-guard)), so it is WebKitGTK's.

**Design.** The shell reads bytes and never decodes them, so decision 5 stands: the webview's
canvas reader stays the one decoder.

1. **Drop.** `tauri.conf.json` keeps `dragDropEnabled` false, which WebView2 needs. A
   `tauri.linux.conf.json`, which Tauri merges over it on Linux only, sets it true, so the native
   handler takes a Linux drop before WebKit does. The shell keeps the paths of the last
   `WindowEvent::DragDrop` drop, and a `dropped_pictures` command reads those paths and no other,
   skipping any that is not a local file: a command that read a path the page names would give
   page script every local file. The overlay listens with `onDragDropEvent` from
   `@tauri-apps/api/webview`, takes a drop whose position is over the composer, and hands the
   bytes to `onAttach`. The command returns base64 as `clipboard_picture` does, and the overlay
   decodes it with `pictureBlob`.
2. `dropGuard.test.ts` reads both config files, and `scripts/ci_paths.py` routes the Linux file
   as it routes `tauri.conf.json`. Record the shell's drop reads in ADR-0070 decision 5.
3. Check it on the Linux shell with the runbook's Linux section: a file dragged from the drag
   source shows a thumbnail, and a link dragged over the window changes nothing.

## History

- 2026-10-06: filed by the Linux shell run of the attached-picture path, which met both gaps
  before it reached the IPC hop and drove the rest with a paste built in the page. A second run,
  with the native drop handler off, showed the drop gap is WebKitGTK's.
- 2026-10-06: the paste half was built: the `ClipboardPicture` port, the X11 adapter that reads
  the owner's `TARGETS` and asks a silent owner once more, the `clipboard_picture` command and the
  overlay's `HostClipboard`. An `xclip` PNG pasted with `Ctrl+V` on the Linux shell showed a
  thumbnail and the cortex read its word. The steps above are the drop half. A Wayland session's
  paste went to [R-805](805-check-a-pasted-picture-on-a-wayland-session.md).
