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
- a copied or dragged file arrives as a `text/uri-list` string, never as a `File`, and the page
  cannot read a `file://` address.

So on the Linux shell a picture cannot be attached at all, while the same overlay in Chromium and,
by ADR-0070's reading, in WebView2 gets a `File` for both.

**Do.** Decide where the bytes come from on this shell, and record it in ADR-0070 decision 5,
which says the shell only passes bytes on. One way: a shell command that reads the clipboard's
image (GTK's `wait_for_image`, or the `arboard` crate on every platform) and returns PNG bytes,
called by the overlay when a paste holds no file; for a drop, the native drop event's paths read
in the shell, which conflicts with the overlay window turning that handler off for WebView2, so
the choice may differ per platform. Either feeds the same canvas reader. Check it on the Linux
shell with the runbook's Linux section.

## History

- 2026-10-06: filed by the Linux shell run of the attached-picture path, which met both gaps
  before it reached the IPC hop and drove the rest with a paste built in the page.
