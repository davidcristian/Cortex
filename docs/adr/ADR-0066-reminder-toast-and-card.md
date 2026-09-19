# ADR-0066: The reminder toast and card

**Status:** Accepted (2026-09-19)

## Context

[ADR-0025](ADR-0025-scheduling-reminders.md) delivers a fired reminder, or a task's outcome, over
two paths: a push to the body through `BodyService.Notify`, and a pull the overlay makes through
`ListDueReminders` when it opens, acked with `AckReminder`. Both render text that **no output
guardrail inspected**: ADR-0015 filters streamed replies, not store rows, and an attacker who gets a
reminder created through injected content writes its text. The body renders the toast behind an OS
trait with per-platform backends (ADR-0011), and the overlay renders the card, acks what the user
dismisses and leads back to the chat the reminder came from.

## Decision

### 1. `Notify` is an OS trait with its Windows backend in `os_windows`

The port is `body_core::os::notify`: `Notify::show(&Notification) -> Result<bool, NotifyError>`,
`Send + Sync` like `AudioControl` because the server holds it across tasks. `LinuxNotify` and
`MacosNotify` are `unimplemented!()` stubs behind the coverage escape hatch. `WindowsNotify`, a
`ToastGeneric` WinRT toast, lives in `os_windows` beside `WindowsHotkey` and `WindowsAudioControl`:
that crate is already the per-platform backend home and already `cfg(windows)`, and the Tauri shell
makes no branching decision, only which backend to construct and from which variable. The server is
`OsService<A: AudioControl, N: Notify>`, constructed by `body_service(audio, notifier, token)`
behind the gRPC token. Activating a WinRT factory needs a COM-initialized thread and the server runs
on tokio workers that have none, so the toast module makes the same idempotent `CoInitializeEx` call
the audio backend does; that call is the only `unsafe` it adds, and it stays COM-only and
`os_windows`-only.

### 2. A notification's text is made inert in the core

`Notification::new` replaces every control character with a space and truncates each line at
`MAX_TEXT_CHARS` (200) with a trailing ellipsis, in the pure core at 100% coverage, so the guarantee
holds for every backend rather than resting on the one file no check reads. A character is replaced
rather than dropped, which would fuse two words across a newline, and long text is truncated rather
than refused, which would lose the reminder to a payload the OS rejects whole.

Escaping is the renderer's step. A toast template is XML, so the Windows backend calls
`os::escape_xml` (the five predefined entities) when it builds the template; a backend rendering
through a markup-limited body, or one that escapes for itself, would show a pre-escaped entity
literally or escape it twice, so `Notification` holds plain text.

### 3. `shown=false` means the host declined

`ToastNotifier.Setting` reports before showing whether notifications are off for this app, this user
or by policy; that answers `Ok(false)`, and a failed show answers `Err`. The brain treats both alike
(the fire stays deliverable for the pull), so the split only keeps the body's own logs accurate.
`NotifyError::Unavailable` and `Backend` map to the statuses `Unavailable` and `Internal`, as
`audio_error_to_status` maps the audio errors.

### 4. Labels about a reminder are fixed app text

A tainted reminder's toast gets one extra line, `from an untrusted source`
(`UNTRUSTED_ATTRIBUTION`, chosen by `Notification::attribution()`), and its card gets an `untrusted
source` badge. Neither is derived from the reminder: whoever writes the text must never write the
label that describes it. For the same reason the card's `open chat` control is a sibling of the text
with an app-authored label, never the text made clickable: a hostile reminder reading `Click here to
verify your account` must not become a working button.

### 5. The toast's app identity is configuration

Windows attributes a toast to an `AppUserModelID` held by an installed Start Menu shortcut, which an
unpackaged app cannot invent. `WindowsNotify::new(app_id)` takes it, and the shell reads
`CORTEX_TOAST_APP_ID`, defaulting to `dev.cortex.body`, the Tauri identifier. A `tauri dev` run has
no such shortcut and borrows a registered identity through the same variable (runbook
[scheduling](../runbooks/scheduling.md)).

### 6. The card is fetched once per summon

`BrainBridge.listDueReminders()` and `ackReminder` run over two Tauri commands
(`src-tauri/src/reminders.rs`). `useReminders(bridge, mode, dispatch)` fetches on the rising edge of
visibility, with a flag that resets on hide. The body starts hidden in the tray and stays resident,
so a fetch on mount would deliver to a window nobody sees; reopening the panel mid-turn does not
fetch again, since the overlay never hid. The list lives in the reducer (`remindersLoaded` replaces
it, since the brain is the authority on each open; `reminderDismissed` removes one id and ignores an
unknown one). A failed list keeps the cards already shown, as the chat list does; the retrying
transport (ADR-0024) has already tried again by then.

### 7. Dismissal is optimistic and acks the fire the card showed

The card leaves the moment it is dismissed and the ack is not awaited, so a slow brain cannot make
the gesture feel stuck. A failed ack is not retried: the fire stays deliverable and the next summon
shows it again. That re-read is also why the transport never retries the ack (ADR-0025 decision 5).
The dismisser takes the whole `DueReminder`, so the ack includes the `fired_at_unix_ms` the card was
pulled with and cannot clear a later fire nobody has seen.

### 8. The card's text is a plain node, never a link

Every field renders as a text node and nothing in the card is turned into a link, because a URL in
reminder text has had no redaction pass. The overlay renders no markup today, so this costs no code;
it is written down because the change that would break it would not show it. The `untrusted source`
badge takes the error bubble's tint at a lower alpha and a dashed border, so it reads apart from the
neutral `repeats` pill without relying on hue. A recurring row says `repeats`, because acking clears
one occurrence and the series is scheduled again; cancelling a series stays a request to the cortex
(`cancel_scheduled`), never a button on this card.

### 9. `open chat` opens the origin session and does not ack

The control passes the row's `session_id` to the switcher's own `onSelectSession` handler, so a
reminder opens a chat exactly as the switcher does. **Opening is not acking**: an ack destroys the
reminder and navigation does not, so a click on the way to the context cannot clear what it came to
explain. The control is absent, not disabled, when the row's `session_id` is empty (a caller with no
session) or names the chat already on screen, where opening would change nothing but cancel the
running turn.

### 10. Card layout

In `overlay.css`: the timestamp sits in a right column under the dismiss control, right-aligned in
the reserved `--time-col` width the switcher's rows share, so text after it does not shift as a card
ages. The column is stretched with `space-between`, so every card is the same height. On the meta
line the `open chat` control leads the badges, pulled left by its hover pill's inset so its first
glyph sits on the title's column, and the line aligns on the baseline, because the pills' asymmetric
padding optically centres their own text and centring the row would lift it off the timestamp's
baseline. The meta line is dropped when a row has no control and no badge. Both icons hang from the
title line's optical centre, the midpoint of its capital and x-height bands; the measurements and
offsets are written beside the rules in `overlay.css`.

## Consequences

- The inert-text rule, the attribution, `escape_xml`, the error mapping, the server's handling of a
  declined toast and the card's behaviour are covered at 100% on Linux; what no check reaches is the
  call sequence into the OS and the look of a real toast and card, which need the Windows host
  ([docs/host/](../host/index.md#windows-desktop)). A toast that appears for a plain reminder but
  not for one containing hostile markup is an escaping break; cards that vanish when the brain goes
  away mean a failed pull is clearing state.
- **Toast activation is not built.** Clicking a toast does nothing: the push path reads back only
  `shown`, and nothing on the body reads a clicked toast. Routing a click to the origin chat needs a
  `session_id` on `NotifyRequest`, passed into the toast's `launch` payload, and on the shell's
  existing `cortex:activate` event, which has no payload today. A click could then be heard through
  the in-process `ToastNotification.Activated` event while the resident body runs, though whether it
  fires for this app's toasts is unmeasured, or through a registered COM activator for a click after
  the process has gone. The payload waits for a second consumer of toast interaction, such as a
  snooze button on the toast, so the wire format is designed with its reader.

## Alternatives rejected

- **The Windows toast in the Tauri shell**: the shell makes no branching decisions, and `os_windows`
  is the backend home.
- **Escaping inside `Notification`**: a backend that escapes for itself would escape twice.
- **A clickable card body**: the text is attacker-written, so its label would be too.
- **A disabled `open chat`**: it invites an explanation there is none worth giving.
- **Retrying a failed ack**: a lost reply would make the retry report nothing to ack.

## Related

- [ADR-0025](ADR-0025-scheduling-reminders.md) (the gRPC contracts these render), ADR-0011 (OS
  backends and the overlay reducer), ADR-0015 (the guardrail this text bypasses), ADR-0023 (the
  brain to body gRPC contract), [body-app](../modules/body-app.md),
  [body-core](../modules/body-core.md), runbook [scheduling](../runbooks/scheduling.md).
