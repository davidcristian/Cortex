# Readings: the Tauri commands over a real IPC hop

What the shell's Rust commands do when the overlay calls them through a real Tauri IPC hop: the
answer to a confirm card, the session reads, the preference record and the link probe. Cited by
[ADR-0011](../adr/ADR-0011-body-v1.md), [ADR-0021](../adr/ADR-0021-session-read-rpcs.md) and
[ADR-0022](../adr/ADR-0022-email-write-confirmer.md). The procedure is the Linux section of
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
  and the countdown bar drained in the first seconds though the preview did not fade. The overlay
  now names the waiting tool there and draws no bar.
- **The hotkey during a turn** hid the window while the overlay stayed in its panel state, so the
  card raised after it was never on screen and the brain denied on its timeout. The next press
  showed the window without a link probe, a chat list refresh or a reminder pull
  ([R-797](../refinements/tasks/797-the-hotkey-hides-the-window-without-telling-the-overlay.md)).
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
