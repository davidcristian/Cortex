# Readings: the Tauri commands over a real IPC hop

What the shell's Rust commands do when the overlay calls them through a real Tauri IPC hop: the
answer to a confirm card, the session reads, the preference record, the link probe, the reminder
pull and the pictures a turn sends. Cited by [ADR-0011](../adr/ADR-0011-body-v1.md),
[ADR-0021](../adr/ADR-0021-session-read-rpcs.md), [ADR-0022](../adr/ADR-0022-email-write-confirmer.md),
[ADR-0066](../adr/ADR-0066-reminder-toast-and-card.md) and
[ADR-0070](../adr/ADR-0070-user-attached-images.md). The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## The commands on the Linux shell

**2026-10-06**, a debug build of the shell from the tree, WebKitGTK drawing in software on an
`Xvfb` display, against a stack built from the tree on the 24 GB card with the shipped cortex
alone, `CORTEX_SCHEDULE_BACKEND=redis`, `schedule_task` named in `CORTEX_TOOLS_GATED` and
`CORTEX_SEAM_CONFIRM_TIMEOUT_S=45`. Every key and click came from `xdotool` and every frame from
`ffmpeg -f x11grab`. The card's SM clock read 0.58 to 0.60 of `clocks.max.sm`; no reading here is a
timing that depends on it.

- **The confirm card** (`confirm_response`). Each reminder request raised a `schedule_task` card
  with the tool name, its three arguments as rows and the reason line. **Approve**: the audit line
  logged `ok=True`, Redis held one `cortex:schedule:<id>` with the requested text due 30 minutes
  later, and the reply said it was set. **Deny**: the audit line logged the `DECLINED` error, no
  schedule key appeared, and the reply relayed the refusal. **Ignored**, with the overlay minimized
  to the orb by Escape: the card raised the preview, which stayed for the whole wait, the brain
  logged `confirmation timed out; denying`, nothing was scheduled, and the reply's preview faded
  after its countdown. One Approve click that came 0.6 s after the brain's timeout scheduled
  nothing.
- **The preview of a pending card** was an empty card: the turn had sent no text before the call,
  and the countdown bar drained in the first seconds though the preview did not fade.
- **The hotkey during a turn** hid the window while the overlay stayed in its panel state, so the
  card raised after it was never on screen and the brain denied on its timeout. The next press
  showed the window without a link probe, a chat list refresh or a reminder pull. These two
  bullets describe the build this section ran; [the next section](#the-window-following-the-overlay)
  has the one that names the waiting tool and hands a press on a shown window to the overlay.
- **The session reads** (`list_sessions`, `session_messages`). `Ctrl+K` listed the five chats in
  the order of the `cortex:sessions` sorted set, newest first, each titled by its first message
  with the last reply as its preview. `Ctrl+Down` twice and `Ctrl+Up` once loaded the second, third
  and second chat's history. After the shell was stopped and started, the first summon showed the
  most recently active chat rather than the one open at the stop.
- **The preference record** (`get_preferences`, `set_preference`). Picking Midnight, Tangent and
  Reverie wrote `overlay.theme`, `overlay.mark` and `overlay.window` to the `cortex:preferences`
  hash, and after a restart the panel came up in all three with the sheet showing them selected.
  Picking Auto removed `overlay.theme` from the hash, and restarts under the default GTK theme and
  under `GTK_THEME=Adwaita:dark` came up light and dark. At the first show after a restart, two
  frames of a 10 frame/s capture were plain white and the third faded into the chosen theme; no
  frame showed the default theme.
- **The link probe** (`check_link`). Green on summon with the brain up. With the brain's container
  stopped, a summon from the hidden state turned the dot red in the second frame of a 4 frame/s
  capture after the press, and the dot dimmed once every 20 frames, which is the 5 s re-check.
  Once the brain was started again the dot went green at the next re-check, with no summon. A
  shell started with a wrong `CORTEX_SEAM_TOKEN` showed amber, its tooltip reading "The brain is
  not serving: Unauthenticated: invalid or missing token".
- **A brain down at the shell's start.** The panel came up in the default appearance with the
  switcher reading "No other chats yet", and both stayed so after the dot turned green: the list
  reloads on a summon or a finished turn, and the appearance at mount only
  ([ADR-0021](../adr/ADR-0021-session-read-rpcs.md) decision 8,
  [ADR-0032](../adr/ADR-0032-preference-record.md)).

Nothing these commands run is Windows code: `confirm.rs`, `sessions.rs`, `preferences.rs`,
`link.rs`, `brain.rs` and `converse.rs` have no `cfg` item, and the overlay's `TauriBridge` is the
same file on both shells. What differs is the webview's transport, WebView2 against WebKitGTK,
which every command shares with the `converse` stream.

Method: `measurements/tauri-ipc-2026-10-06/`, holding the scripts that ran the shell and drove it
(`scripts/`), the event log, frames in `shots/`, the dot captures in `dot-outage/` and
`dot-recovery/`, the brain's log and the Redis reads.

## The window following the overlay

**2026-10-06**, the same rig an hour later, with the shell sending `cortex:toggle` for a press on a
shown window and the overlay calling `set_overlay_shown`. Window visibility was read with
`xdotool search --onlyvisible --name '^Cortex$'`.

- **A press during a turn** hid the window within 0.6 s. When `schedule_task` asked, the window came
  back with the preview reading "Waiting for your approval to run schedule_task" and no bar. A
  click opened the panel on the card, Approve was clicked, the audit line logged `ok=True`, and
  Redis held one `cortex:schedule:<id>` with the text `stretch` due 30 minutes later.
- **The summon after a hotkey hide.** A press over the idle panel hid the window, the brain's
  container was stopped, and the next press showed the panel with the dot green in the first frame
  of a 4 frame/s capture that showed it and red from the next on, which is the summon's probe.
- **Escape** left the window shown at 0.1 s and hidden at 0.7 s, and the next single press summoned.
- **Escape during a turn** left the window shown with the orb, and a press opened the streaming
  panel.

Method: `measurements/tauri-ipc-2026-10-06/after-fix/`, with the scripts, the event log, frames in
`shots/` and the dot capture in `dot-outage/`.

## Attached pictures and reminder cards

**2026-10-06**, the same rig with the cortex started with its projector
(`CORTEX_MODEL_FILE_CORTEX_MMPROJ` set, `CORTEX_VISION` at its default), `schedule_task` not
needing approval, and WebKitGTK 2.52.6. A temporary listener in the page reported each `paste`,
`dragenter` and `drop` event's types and files to a local server. No reading here is a timing.

- **A picture on the X clipboard** reached the overlay as nothing. Bytes offered by `xclip` under
  `image/png`, and a GTK `set_image` offering `image/png`, `image/jpeg`, `image/bmp` and twelve more
  image targets, each gave a `paste` event with no types and no files, so nothing was attached. A
  file URI under `text/uri-list` came through as a string item, not a file. Plain text pasted
  normally.
- **A file dragged from a GTK drag source** offering `text/uri-list`, under the shipped window
  config, gave the page a `dragenter` whose types were `text/uri-list` and `text/html` with no file,
  and no `drop` event: wry's WebKitGTK drop handler, which Tauri installs unless `dragDropEnabled`
  is false, returns true on a drop and stops WebKit's own. With `dragDropEnabled` set to false in a
  local build, the `drop` reached the page with the same two string types and no file, and WebKit's
  default put the file's `file://` address into the field as text. A second drag, from a source
  offering file manager targets, navigated the window to the dropped JPEG. The Windows backend of
  wry instead replaces WebView2's drop target and calls `SetAllowExternalDrop(false)` whenever that
  handler is installed.
- **A paste built in the page.** To drive the rest of the path, the listener fetched each test
  file, wrapped it in a `File` with a name and a type, and dispatched a `paste` holding it on the
  focused field. From there every step was the shipped code: `onPaste`, the canvas reader, the
  `images` argument of `converse`, the shell's base64 decode and the brain.
- **Two pictures.** A 1920 by 1080 PNG and a 1280 by 960 JPEG showed as two thumbnails. The reply
  described both: a red square on a blue background, and two rectangles side by side on white.
  The stored user message ended `(Attached to this message and not kept: image/png 1600x900,
  image/jpeg 1280x960.)`, which is the canvas's 1600 px downscale of the PNG and the JPEG kept as
  JPEG, and a chat reopened with `Ctrl+N` then `Ctrl+Down` showed that note under the question.
- **A mislabelled file**, named `mislabelled.png` and typed `image/png` but holding a 1024 by 768
  JPEG, was attached, and the reply named its two colours. The note read `image/png 1024x768`:
  the canvas decodes whatever the bytes are and encodes PNG for any type but JPEG, so the brain's
  signature check receives a real PNG and has nothing to refuse. Only a client that sends bytes
  without decoding them can reach that check.
- **A refusal.** With the brain recreated under `CORTEX_VISION=off`, a question with two pictures
  ended at once: the brain logged `refusing a turn whose pictures the model cannot see`, the
  composer showed its sentence above both thumbnails with the question back in the field, the
  title read "New chat" again, and the session set held only the earlier chat. After `Ctrl+N` the
  new, empty chat still showed that sentence over no pictures.
- **Reminder cards.** The cortex scheduled a one-shot `stretch`, a `drink water` repeating every
  60 s, and, from a turn holding a picture, a third whose stored record was `tainted`. With the
  overlay hidden until all three had fired, a summon over the chat that held those turns showed no
  card, though `ListDueReminders` returned three: the stack opens only on a chat with no messages.
  After `Ctrl+N` the three cards stood above the empty chat's opening screen, each with its text
  and its age, `repeats` on the series and the dashed, red-tinted `untrusted source` badge on the
  tainted one. Dismissing `stretch` removed its card and deleted its `cortex:schedule:<id>`
  record, and the next list held the other two. With the brain's container stopped, an Escape and
  a summon turned the dot red and both cards stayed.

Method: `measurements/tauri-ipc-2026-10-06/pictures-and-reminders/`, with the scripts (the drag
source, the clipboard owners, the listener's server and the vision override), the test pictures,
the event log, the listener's log, frames in `shots/` and the Redis and `ListDueReminders` reads.

## The drop guard

**2026-10-06**, the same rig with the overlay window's `dragDropEnabled` set to false and the
overlay's window-level drop guard (`dropGuard.ts`) installed, and no brain. Each source dragged
`drop.jpg` onto the field and onto the empty panel above it; the listener reported each `drop`
event's types and files, whether its default was cancelled, the field's text 300 ms later and the
page address.

- **With the guard**, from the source offering only `text/uri-list` and from the one offering file
  manager targets, every `drop` reached the page with the types `text/uri-list` and `text/html` and
  no file. The guard cancelled each one: the field stayed empty and the window stayed on the
  overlay. WebKitGTK gives the page no `File` for a dropped file with Tauri's handler off as well.
- **Without it**, in the same build with the guard's effect replaced through Vite's hot reload, a
  drop on the field put the file's `file://` address into it, and a drop on the panel opened the
  JPEG as the whole window with no `drop` event reaching the page.

Method: `measurements/tauri-ipc-2026-10-06/drop-guard/`, with the scripts, the listener's log and
frames in `shots/`.
