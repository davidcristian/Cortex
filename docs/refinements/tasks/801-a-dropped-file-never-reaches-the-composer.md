# A dropped file never reaches the composer

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md) decision 7
**Verified:** 2026-10-06

The composer takes a dropped picture from the webview's HTML `drop` event (`onDrop` in
`body/app/src/components/Composer.tsx`). The overlay window in `body/app/src-tauri/tauri.conf.json`
leaves Tauri's `dragDropEnabled` at its default, true, which installs wry's native drop handler,
and that handler takes the drop before the page sees it:

- **Windows.** wry 0.55 (`src/webview2/mod.rs` and `drag_drop.rs`) calls
  `SetAllowExternalDrop(false)` on the WebView2 controller and registers its own `IDropTarget`, so
  an Explorer drop becomes a `tauri://drag-drop` event with paths, which nothing in the overlay
  reads. Tauri's own config doc says disabling the handler "is required to use HTML5 drag and
  drop on the frontend on Windows". This half is read from the source and not run.
- **Linux.** The WebKitGTK handler (`src/webkitgtk/drag_drop.rs`) returns true on a drop, which
  stops WebKit's own; on the Linux shell the page got a `dragenter` and no `drop`
  ([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)).

Turning the handler off is not enough on its own. In a local build with `dragDropEnabled: false`,
a drag whose types the composer does not claim (it claims only `Files`) put the file's `file://`
address into the field as text when dropped there, and navigated the whole window to the file
when dropped beside it, which is the failure the attached-picture host check names.

**Do.** Set `"dragDropEnabled": false` on the overlay window, and add a window-level guard in the
overlay that cancels `dragover` and `drop` for any drag holding `Files` or `text/uri-list`, so
nothing the composer does not take can navigate the window; a plain text drag keeps its default.
Cover the guard in Vitest, check on the Linux shell that a file drag no longer navigates, and
leave the Explorer drop to [H-024](../../host/tasks/024-attached-picture-over-ipc.md).

## History

- 2026-10-06: filed by the Linux shell run of the attached-picture path, which drove a drop from a
  GTK drag source under both settings.
