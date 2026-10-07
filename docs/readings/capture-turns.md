# Readings: capture turns through the Linux shell

Turns that call `capture_screen` through a real body, the debug Linux shell and its X11 backend,
with the cortex and its projector on the card. They show what the brain, the model, the receipt,
the refusal sentence and the overlay's capture indicator do with a real picture. They show nothing
about the GDI copy, `WDA_EXCLUDEFROMCAPTURE` or the Win32 Z-order walk, which only the Windows
shell runs: those stay with [windows-capture](../host/index.md#windows-capture). Cited by
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md).

## Method

**2026-10-07.** `Xvfb` at 1600 by 1000 with no window manager, and one titled Tk window, 1000 by
560 at 40, 300, showing a `cargo run` E0308 error in 16 px type, its right part under the overlay.
The shell ran as the [overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless)
says, with `CORTEX_HOST_CAPTURE=1`, `CORTEX_BODY_ADDR=0.0.0.0:40151` and a freedesktop
notification server on its session bus that logs every `Notify` call. The stack was
`docker-compose.yml`, `docker-compose.gpu.yml` and `docker-compose.body.yml` with
`CORTEX_BODY_ENDPOINT=host.docker.internal:40151` and the cortex projector named; the engine
reported build `b11434`. Three turns were typed into the overlay with `xdotool`. The rest were sent
by a script calling `BrainService.Converse` from inside the brain container, one fresh session a
question, timing each `ServerEvent` from the send. The overlay stayed shown for every turn. The
median SM clock over the busy samples was 0.58 of the card's maximum during the latency rows and
0.60 during the target rows, with the display awake. Drivers, rows and frames:
`measurements/capture-turns-2026-10-07/`.

## The overlay is not in the picture

Asked "what's on my screen?" with the panel open over the Tk window and a prior reply, "violet
pelican seven", on it, the cortex described "a terminal window with a Rust compilation error" and
guessed at what the panel covered: `read_to_string` for `read_total()`, and a `Result` for the
hidden "found `String`". None of the 25 scripted capture replies named the panel, its prior reply
or any of its words. This is the model's view of the X11 backend painting the shell's windows
black; the pixel counts are in [x11-overlay-capture](x11-overlay-capture.md).

## The receipt and the reply

Each of the 28 captures that succeeded sent one `Notify` with the summary "Screen captured", and no
other turn sent one. A display target's body was "A picture of your screen was sent to the
assistant." and a focus target's "A picture of one window was sent to the assistant." The focus
capture typed into the overlay, "what does the error in the window in front of me say?", gave the
window sentence and a reply that began "The error in the window says:", quoted
`error[E0308]: mismatched types` and `--> src/main.rs:14:22`, and said the rest was cut off in the
screenshot: inside the crop the panel's rectangle is black on X11 as well.

## Which target the cortex picks

Ten questions about one window, five phrasings asked twice ("what does the error in the window in
front of me say?", "read me the error message in the window I'm looking at", "what line does the
compiler error in this window point at?", "can you read the error in the window in front of me?",
"transcribe the first error line in the window I have open"), alternated with ten about the screen
("what's on my screen?", "describe my screen", "what am I looking at on my screen right now?",
"give me an overview of everything on my screen", "what's on my display?"). Each called
`capture_screen` once and each call succeeded. The receipt names the target here, since the Tk
window does not fill the display: the window questions picked `focus` 10 of 10 times and the screen
questions `display` 10 of 10.

## The switch off

With `CORTEX_HOST_CAPTURE` unset the shell printed `cortex: screen capture is off
(CORTEX_HOST_CAPTURE=1)` at start. "what's on my screen?", typed once and sent once by the script,
called `capture_screen`; its `ToolOutcome` came back `ok: false`, no `Notify` was sent, and the
reply was "I'm sorry, I'm unable to see your screen because screen capture is disabled on this
host." The last clause is the body's `PermissionDenied` detail, which the brain sends after "the
body refused to capture the screen"; neither reply said the body could not be reached. The
header's capture indicator showed the open ring ("asked") from the call until the turn ended, and
with the switch on it showed the ring with its pupil ("read"). Both went out when the turn ended.

## Where a capture turn's time goes

Five text turns, "In two sentences, what does Rust's E0308 mismatched types error mean?",
alternated with five capture turns, "what's on my screen?", each in a fresh session. Medians, as
shares of the capture turn's time to its first reply text:

| Interval of a capture turn | Share |
| --- | --- |
| The first inference pass, from the send to the `capture_screen` call | 0.55 |
| The call as the brain sees it: gRPC to the body, the X11 read and encode, the reply checked | 0.12 |
| The second inference pass, from the tool result to the first reply text | 0.33 |

- The call's share was 0.12 to 0.14 in each of the five turns, so the model's two passes are about
  seven eighths of the time before the reply starts.
- Every text turn thought before it answered. Its first text came 2.48 times as late as a capture
  turn's and it ended 1.68 times as late, though the capture replies were longer (424 to 521
  characters against 281 to 349). How a capture turn compares with a text turn therefore depends
  on how long the text question makes the cortex think, not on the picture.
- Over the twenty target rows a focus capture's call took 0.62 of a display capture's (medians),
  the crop being smaller to read and encode.
