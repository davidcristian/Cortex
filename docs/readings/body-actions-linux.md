# Readings: volume and reminder pushes through the Linux shell

Turns in which the dockerized brain dials the body's `BodyService`: the cortex's `set_volume` and
`get_volume`, and a fired reminder's push over `Notify`. They ran against the debug Linux shell,
whose server uses `LinuxAudioControl` over `pactl` and `LinuxNotify` over the session bus. They
show what the cortex emits, the brain's dial into the shell's server, the ticker's ack on a
delivered push and the overlay's reminder cards. They show nothing about Core Audio, the WinRT
toast, its `AppUserModelID` or the Windows firewall, which stay with
[H-002](../host/tasks/002-core-audio-volume-action.md) and
[H-003](../host/tasks/003-real-reminder-toast.md). Cited by
[ADR-0023](../adr/ADR-0023-body-gateway-volume.md) and
[ADR-0066](../adr/ADR-0066-reminder-toast-and-card.md).

## Method

**2026-10-07.** `Xvfb` at 1600 by 1000 and the debug shell as the
[overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless) says, with
`CORTEX_BODY_ADDR=0.0.0.0:23151`: `ss -ltnp` showed `cortex-body` listening there and its log had
no bind failure. The shell had `PULSE_SERVER=unix:/mnt/wslg/PulseServer`, the PulseAudio server
WSLg runs, and on `PATH` a `pactl` from `pulseaudio-utils` 16.1, unpacked with `dpkg-deb -x`. On
its session bus a notification server written with Gio listed the capabilities `body` and
`body-markup` and logged every `Notify` call. The stack was `docker-compose.yml`,
`docker-compose.gpu.yml` and `docker-compose.body.yml` with `CORTEX_SCHEDULE_BACKEND=redis` and
the cortex alone on the card (engine build `b11434`). Two requests were typed into the overlay
with `xdotool`; the rest were sent by a script calling `BrainService.Converse` from inside the
brain container, one fresh session a request. `pactl get-sink-volume` read each result back and
`pactl subscribe` logged every change to the sink. Drivers, logs and frames:
`measurements/body-actions-2026-10-07/`.

## Volume

| Request | The brain's audit line | `pactl` afterwards | Reply |
| --- | --- | --- | --- |
| "set volume to 30%" | `set_volume {"level":0.3}` | 19661, 30% on both channels | "OK. I've set the volume to 30%." |
| "what's my volume?", a fresh session | `get_volume {}` | unchanged | "Your volume is currently at 30%." |
| "mute my sound" | `set_volume {"mute":true}` | muted, still 30% | "OK. I've muted your sound." |
| "unmute my sound" | `set_volume {"mute":false}` | not muted | "OK. I've unmuted your sound." |
| "set volume to 55%", typed in the overlay | `set_volume {"level":0.55}` | 36045, 55% | "OK. I've set the volume to 55%." |

- Every call ended `ok: true` and no turn sent a `ConfirmRequest`. The overlay showed the typed
  turn's reply with no approval card.
- `pactl subscribe` logged one sink change for each `set_volume` call and one for the restore to
  100% by hand afterwards, and no other.

## Reminder pushes

- **A plain reminder.** "remind me to stretch in one minute", typed into the overlay, called
  `schedule_task` with `{"in_seconds":60,"kind":"reminder","text":"stretch"}`. Within one ticker
  pass of its due time (`CORTEX_SCHEDULE_POLL_S`, 5 s) the notification server logged `Notify`
  with the application `Cortex`, the summary `Cortex reminder`, the body `stretch` and the
  server's own expiry, `-1`.
- **A reminder whose text is markup.** "remind me in one minute to read `<b>bold</b> & "quotes"`"
  stored that text unchanged, and its `Notify` body was
  `read &lt;b&gt;bold&lt;/b&gt; &amp; &quot;quotes&quot;`: escaped, because the server listed
  `body-markup`, so a server rendering markup shows the characters as typed.
- **No card afterwards.** `ListDueReminders` then returned no reminders, and the overlay's empty
  chat showed no card.
- **The control.** With the notification server stopped, so that nothing owned
  `org.freedesktop.Notifications` on the bus, a third reminder ("drink water") fired and the brain
  logged `push failed; pull will deliver` with `org.freedesktop.DBus.Error.ServiceUnknown`.
  `ListDueReminders` returned it, the overlay's empty chat showed its card, and the card's check
  button acked it, after which the list was empty. The missing cards above are therefore the ack
  on a delivered push, not a pull that shows nothing.

## The interval on a one-shot reminder

Nine one-shot requests reached `schedule_task`: the three above and six more, such as "remind me
to call the dentist in 30 minutes", each with its delay as `in_seconds`. One first call, the
markup reminder's, also sent `every_seconds: 0`. The tool refused it with "'every_seconds' must be
a number between 60 and 315360000", and the cortex's next call, without the field, succeeded.
`edit_scheduled` reads the same `0` as "stop repeating"
([R-809](../refinements/tasks/809-schedule-task-refuses-a-zero-interval.md)).
