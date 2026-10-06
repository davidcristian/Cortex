# Runbook: the overlay and the Tauri shell

Three ways to run the body overlay: in a plain browser against a fake bridge, with no host and no
Tauri, which is what CI and `just check-overlay` cover; as the real Tauri app on Windows, with the
global hotkey and the real brain, which only the host can run; and as the Linux shell on a headless
display, which the agent drives against the real brain. Tauri is a GUI with a webview and a real OS
event loop, so it is never run in CI ([ADR-0011](../adr/ADR-0011-body-v1.md)).

## In a browser, with no host and no Tauri

```bash
cd body/app
npm ci
npm run dev            # vite on http://localhost:5173; the overlay self-summons on load
```

The page mounts with `DemoBridge`, a canned streamed reply, and dispatches `cortex:activate` once,
so the design is visible immediately. This is the loop for iterating on look and feel
([overlay-ux.md](../design/overlay-ux.md)). A prompt containing "send" or "email" walks the
scripted confirmation round: the reply pauses on the approval card, and Approve or Deny steers how
the canned turn ends. A prompt containing "offline" or "degraded" scripts a connection outage for
the header dot: the demo brain reports that state for 12 s, so red, amber, the pulse while a probe
is out, and the recovery re-check flipping back to green can all be driven by hand. A pasted or
dropped picture shows as a thumbnail in the composer, and a prompt containing "refuse" sent with one
comes back refused, with the text and pictures handed back. The check runs the same code path:

```bash
just check-overlay     # npm ci + tsc --noEmit + Vitest at 100% line and branch coverage
```

## The Tauri app on Windows

This section is the procedure;
[docs/host/index.md#windows-desktop](../host/index.md#windows-desktop) is the checklist that says
which of these are still owed, what each proves, and where the result goes.

You need Rust (stable), Node with `body/app` dependencies installed (`npm ci`), the WebView2
runtime (preinstalled on Windows 11, otherwise install the Evergreen runtime), and the brain
reachable at `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`), through `just up-gpu` for the
real resident cortex or `just brain-serve` for a native brain. The Tauri CLI is a devDependency,
so `npm run tauri …` works with no global install.

The full platform icon set is committed under `src-tauri/icons/`, including the Windows `icon.ico`
that `tauri-build` needs even for `dev`, so there is nothing to do. To rebrand, regenerate from
any square source image of at least 1024 by 1024 and commit the result:

```powershell
cd body/app
npm run tauri icon path\to\logo.png
```

Then run it:

```powershell
cd body/app
npm run tauri dev      # builds the shell, starts vite, opens the hidden overlay window
```

And check the loop end to end.

1. Press **Ctrl+Alt+Space**, or whatever `CORTEX_HOTKEY` names. The overlay appears and takes
   focus; press again to hide. The tray icon's **Show overlay** does the same, and **Quit Cortex**
   exits.
2. Type a prompt and send. The reply streams in token by token, with the violet glow while it
   works, then settles back to the resting state.
3. Confirm that follow-ups keep context. The brain persists session state, and each turn is a
   fresh `Converse` sharing the app's `session_id`.
4. **The approval flow**, which needs the email sidecar's write path enabled on the stack
   (`CORTEX_EMAIL_SEND_ENABLED=true` plus SMTP credentials, see
   [email-imap.md](email-imap.md)). Ask for a send, such as "email ada a quick hello". The reply
   pauses on the approval card, showing the tool name, the draft as key and value lines, and the
   reason. Approve and the send runs and the reply reports it sent; deny and the reply relays that
   it was not sent. Then check that it fails closed: trigger another approval and ignore it, or
   dismiss to the orb. The brain denies on timeout, 120 s by default, and the reply says the user
   declined. An approval arriving while minimized surfaces the preview, which must not auto-fade
   while the question is open. A turn that fails while minimized, such as one cut off by
   `just down`, surfaces a preview showing the error, which stays until it is clicked or dismissed.
5. **The connection indicator.** The header dot is green on summon while the brain is up. Stop the
   brain (`just down`) and summon again: it turns red within the retry budget and stays red,
   re-checking every 5 s while the panel is open. Start the brain again and the dot goes green on
   its own, without a re-summon. The chat list does not refresh with it: it reloads on a summon and
   when a turn ends, so a list that was empty stays empty until then. Point `CORTEX_BRAIN_ADDR` at
   a live brain with the wrong `CORTEX_SEAM_TOKEN` to see amber instead of red: the brain answered
   `Unauthenticated`, so it is reachable and rejecting the token.

Override the address or the chord as needed, and if the brain runs with a token set the same
variable for the shell before `tauri dev`, or an untokened body gets `Unauthenticated` on every
call:

```powershell
$env:CORTEX_BRAIN_ADDR = "http://127.0.0.1:50051"
$env:CORTEX_HOTKEY = "ctrl+alt+space"
$env:CORTEX_SEAM_TOKEN = "<the same secret the brain serves with>"
npm run tauri dev
```

## The Tauri app on Linux, headless

The Linux shell runs the overlay, the Tauri commands and the gRPC client that the Windows shell
runs, so a real IPC hop can be driven on the development machine with no desktop and no sudo:
WebKitGTK draws in software on an `Xvfb` display, `xdotool` types and clicks, and `ffmpeg` grabs
frames. [The Tauri command readings](../readings/tauri-ipc-commands.md) and
[the overlay's view of a handoff](../readings/model-swap.md#the-overlays-view-of-a-handoff) were
taken this way.

1. **The library prefix.** Build the userspace prefix of the
   [shell clippy readings](../readings/shell-clippy.md): `apt-get download` of the closure of the
   WebKitGTK, GTK, appindicator, librsvg and D-Bus development packages plus `xdotool`, each one
   extracted with `dpkg-deb -x` into a directory outside the repo.
2. **Build.** In `body/app/src-tauri`, run `cargo build --locked` with `PKG_CONFIG_PATH` naming the
   prefix's two `pkgconfig` directories, and `RUSTFLAGS` set to `-L native=<links>` plus
   `-C link-arg=-Wl,-rpath-link,<prefix>/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu`, where
   `<links>` is a directory of absolute links to each `.so` in the prefix.
3. **The stack and the page.** Start the brain stack with its own project name
   (`docker compose -p <name> ...`) and `CORTEX_SEAM_TOKEN` set, then `npm run dev` in `body/app`:
   a debug build loads the overlay from `devUrl`, `http://localhost:5173`.
4. **The display.** `Xvfb :78 -screen 0 1600x1000x24`. The 640 by 720 window opens centred, at
   (480, 140) on that screen.
5. **The shell**, with `DISPLAY=:78`, `GDK_BACKEND=x11`, `WAYLAND_DISPLAY` unset,
   `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`, `XDG_DATA_HOME` pointing at an empty directory and
   the stack's `CORTEX_SEAM_TOKEN`, started as the next paragraph shows.
6. **Drive it.** `xdotool key ctrl+alt+space` summons, and `mousemove X Y click 1`, `type` and
   `key` do the rest; `xdotool` from the prefix needs the prefix's library directory on
   `LD_LIBRARY_PATH`. `ffmpeg -f x11grab -video_size 1600x1000 -i :78 -frames:v 1 shot.png` grabs
   a frame, and `-framerate 4 -t 30` in place of `-frames:v 1` a sequence.
7. **Stop it.** Stop the shell by its exact name, `pkill -x cortex-body`: `pkill -f` with the
   binary's path also matches the shell that runs the command. Then stop `Xvfb`, the Vite server
   and the stack (`docker compose -p <name> down -v`). A shell killed with its session bus can
   leave `dbus-daemon` and `at-spi-bus-launcher` behind; stop those by pid.

**The shell's start.** WebKitGTK starts its helper processes from the compiled-in
`/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1`, so the shell runs in a user and mount namespace that
overlays the prefix's library directory on the system one:

```
unshare --user --map-root-user --mount bash -c "mount -t overlay overlay \
  -o lowerdir=<prefix>/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu \
  /usr/lib/x86_64-linux-gnu && exec dbus-run-session -- target/debug/cortex-body"
```

`GDK_BACKEND=x11` is required: without it, with `WAYLAND_DISPLAY` unset and WSLg's `wayland-0`
socket in `XDG_RUNTIME_DIR`, no window appeared on `Xvfb`, which fits GTK opening that socket while
the shell grabbed the chord on X. A notification server such as `dunst` started inside the same
`dbus-run-session` shows `Notify`, and `pactl` on `PATH` serves the volume.

A press opens the panel even with no brain reachable, and its link dot shows red. Avoid a plain
static server of `body/app/dist`: git ignores that directory, so it holds whatever build last ran
there. WebKitGTK also keeps pages in a disk cache under
`$XDG_DATA_HOME/dev.cortex.body/WebKitCache`, by default in `~/.local/share`, and serves a page
whose server sent no `Cache-Control`, such as `python3 -m http.server`, from that cache without a
request, even after Vite holds the port. If the window shows only the stage and the panel never
opens, delete that directory or point `XDG_DATA_HOME` at an empty one.

**Pictures.** WebKitGTK gives the page no file for a picture on the clipboard or a dragged file
([R-802](../refinements/tasks/802-the-linux-shell-attaches-no-pasted-or-dropped-picture.md)), so a
run of the attached-picture path appends a listener to `src/main.tsx` that fetches a test file,
wraps it in a `File` inside a `DataTransfer`, and dispatches a `paste` holding it on the focused
field. Everything after that event is the shipped code. Remove the listener after the run.

## Notes

**What is already proven, and what is still the user's to confirm.** The frontend (prompt to
stream to render, the mode machine, theming) is browser-checked here and covered at 100%. Steps 2
to 5 ran on the Linux shell, through a real Tauri IPC hop
([readings](../readings/tauri-ipc-commands.md)). Still the user's to confirm on Windows: the
`os_windows` `global-hotkey` registration, the tray, window show and hide, a turn streaming
through WebView2, whose transport every command shares, and a picture pasted or dropped into
WebView2.

**What a stalled turn looks like, and when the body gives up on one.** A turn has no time limit:
the reply may take as long as the model and its tools take, and the thinking indicator stays up
while the brain keeps sending. While a turn runs, the brain sends a heartbeat every 30 s in which it
has nothing else to send. It repeats what the turn waits on, and the status chip shows its
sentence: a model generating (`thinking`), a subtask waiting for room in the subagent budget
(`queued`) or running (`delegating`), the deep model loading or the cortex coming back
(`swapping`), the earlier conversation being summarized (`folding`), a tool call running
(`calling`), or an approval card waiting for you (`asking`). So a chip left stale by a dropped
status is set right within 30 s. If nothing at all arrives for
`CORTEX_BRAIN_TURN_HEARTBEAT_GAP_MS` (default 120000, two minutes), the brain or the path to it has
stopped, and the body stops waiting: the reply settles on whatever text arrived, with
`no reply within 120s`, and the header dot goes red with the same line. A brain that is alive but
whose turn sends nothing except heartbeats is given longer: `CORTEX_BRAIN_TURN_FIRST_GAP_MS`
(default 600000, ten minutes) before the first event, or `CORTEX_BRAIN_TURN_IDLE_GAP_MS`
(default 14400000, four hours) mid reply, and then settles the same way. The user never has to
wait for any bound, since the Stop control ends a turn in place at any time, keeping the partial
text and recording no error.

The mid-stream default is long because it has to clear a delegated subtask, which may wait two
hours for the CPU budget and then hold that admission for two runs of forty minutes without the
brain sending anything. A stack composed without the subagent sidecars never produces that
silence, so turn it down: `CORTEX_BRAIN_TURN_IDLE_GAP_MS=600000` matches the first-event bound and
settles a wedged turn in ten minutes instead of four hours.

Run the body and the brain from the same build. An older brain sends no heartbeats, so a newer body
ends every turn that is quiet for two minutes; setting `CORTEX_BRAIN_TURN_HEARTBEAT_GAP_MS=14400000`
restores the old bounds until the brain is rebuilt. An older body reads the first heartbeat as a
protocol error and ends the turn. The same builds renamed the call behind the switcher's hoist
toggle to `SetSessionHoisted`, so across the two builds that toggle fails with `UNIMPLEMENTED` in
either direction and the list keeps its grouping; the listing itself still shows which chats are
hoisted, because the field kept its number.

**The window in v1** is a fixed 640 by 720 frameless opaque always-on-top window, and the hotkey
toggles it, with no hide-on-blur, so a check is predictable. Deferred to a later overlay-polish
pass, all together: a transparent window so only the panel floats (a first attempt bled through
the panel content and left a window border, so it needs doing properly with click-through),
click-through margins, hide-on-blur, and the morph to a real screen-corner orb. The CSP is `null`
for v1, a fully local app loading only bundled assets; tighten it once the IPC and dev allow-list
are settled on the host.

**If the hotkey collides** with other software, set a different `CORTEX_HOTKEY`. A registration
failure is logged to stderr and is not fatal, and the tray still summons the overlay. If
`global-hotkey` event delivery ever misbehaves, the fallback is Tauri's `global-shortcut` plugin
behind the same unchanged `Hotkey` port.

**On Linux** the shell grabs the chord on the root window of the X display that `DISPLAY` names,
so a press toggles the overlay whichever window has focus. A chord another X client has grabbed
fails with `BadAccess` and is logged like any other registration failure. On a Wayland session,
where `WAYLAND_DISPLAY` is set and not empty, the shell binds the chord another way, because
Xwayland is assumed to get a key only while one of its own windows has focus. Where
`org.kde.kglobalaccel` runs, as on KDE Plasma, it registers the chord there as an action of the
component "Cortex" named by the chord's text, such as `ctrl+alt+space`, which System Settings'
shortcuts page lists; a chord another program holds fails and is logged. Elsewhere it binds
through the desktop portal's `GlobalShortcuts`. The compositor may ask the user to confirm or
change the trigger, so the trigger that toggles the overlay can differ from `CORTEX_HOTKEY`; the
description it shows the user is "Show or hide the Cortex overlay". The bind runs on its own
thread and fails if the portal has not answered within a minute. Of the Ubuntu 24.04 archive's portal backends only
`xdg-desktop-portal-kde` implements the interface, and on Plasma 5.27 it binds nothing, which is
why KDE goes through `kglobalaccel`; where no backend does, the registration fails and is logged.
