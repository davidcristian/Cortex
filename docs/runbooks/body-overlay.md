# Runbook: the overlay and the Tauri shell

Two ways to run the body overlay: in a plain browser against a fake bridge, with no host and no
Tauri, which is what CI and `just check-overlay` cover; and as the real Tauri app on Windows, with
the global hotkey and the real brain, which only the host can run. Tauri is a GUI with a webview
and a real OS event loop, so it is built and checked on the host, never in CI
([ADR-0011](../adr/ADR-0011-body-v1.md)).

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
is out, and the recovery re-check flipping back to green can all be driven by hand. The check runs
the same code path:

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
   while the question is open.
5. **The connection indicator.** The header dot is green on summon while the brain is up. Stop the
   brain (`just down`) and summon again: it turns red within the retry budget and stays red,
   re-checking every 5 s while the panel is open. Start the brain again and the dot goes green on
   its own, without a re-summon, and the chat list fills in with it. Point `CORTEX_BRAIN_ADDR` at
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

## Notes

**What is already proven, and what is still the user's to confirm.** The frontend (prompt to
stream to render, the mode machine, theming) is browser-checked here and covered at 100%. Still
the user's to confirm on Windows: the `os_windows` `global-hotkey` registration, the tray, window
show and hide, the real `converse` command streaming a live brain turn to the webview, the
`confirm_response` command taking an approval back into the open turn, and the `check_link`
command behind the indicator, whose classification is covered in `body_core::link` and checked
against a real brain by the `body-rpc` live suite, so what Windows adds is the IPC hop.

**What a stalled turn looks like, and when the body gives up on one.** A turn has no time limit:
the reply may take as long as the model and its tools take, and the thinking indicator stays up
while the brain keeps sending. While a turn runs, the brain sends a heartbeat every 30 s in which it
has nothing else to send, and the overlay does not show it. If nothing at all arrives for
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
