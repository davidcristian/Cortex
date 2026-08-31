# Runbook for the overlay + Tauri shell (Slice 8 host half, ADR-0011)

Two ways to run the body overlay: **(A)** in a plain browser against a fake bridge, with no host, no
Tauri, fully CI-gated; and **(B)** the real Tauri app on Windows, with the global hotkey and the
real brain seam.
(A) is what CI and `just check-overlay` exercise; (B) is the host-only half. Tauri is a GUI with a
webview and a real OS event loop, so it is built and validated on the host, never in CI (ADR-0011).

## A. Browser dev (no host, no Tauri)

```bash
cd body/app
npm ci
npm run dev            # vite on http://localhost:5173; the overlay self-summons on load
```

The page mounts with `DemoBridge` (a canned streamed reply) and dispatches `cortex:activate` once,
so the design is visible immediately. This is the loop for iterating on look/feel
([overlay-ux.md](../design/overlay-ux.md)). A prompt containing "send" or "email" walks the
scripted **confirm round** (ADR-0022): the reply pauses on the approval card, and Approve/Deny
steers how the canned turn ends. A prompt containing "offline" (or "degraded") scripts a
**connection outage** for the header dot (ADR-0011 addendum): the demo brain reports that state
for 12 s, so red/amber, the pulse while a probe is out, and the recovery re-check flipping back
to green are all drivable by hand. The gate is the same code path:

```bash
just check-overlay     # npm ci + tsc --noEmit + Vitest at 100% line+branch
```

## B. The Tauri app on Windows (host validation)

This section is the procedure; [docs/host/index.md#windows-desktop](../host/index.md#windows-desktop) is the
checklist that says which of these are still owed, what each proves, and where the result goes.

### Prerequisites (Windows)

- **Rust** (stable) + **Node** (with the repo's `body/app` deps installed: `npm ci`).
- **WebView2 runtime** (preinstalled on Windows 11; otherwise install the Evergreen runtime).
- The **Tauri CLI** is a devDependency, so `npm run tauri …` works with no global install.
- The **brain** reachable at `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`) via e.g.
  `just up-gpu` for the real resident cortex, or `just brain-serve` for a native brain.

### Icons

The full platform icon set is committed under `src-tauri/icons/` (a placeholder orb identity),
including the Windows `icon.ico` that `tauri-build` needs even for `dev`. Nothing to do. To
rebrand, regenerate from any square source image (ideally ≥1024×1024) and commit the result:

```powershell
cd body/app
npm run tauri icon path\to\logo.png
```

### Run it

```powershell
cd body/app
npm run tauri dev      # builds the shell, starts vite, opens the hidden overlay window
```

Then validate the loop end to end:

1. Press **Ctrl+Alt+Space** (or `CORTEX_HOTKEY`). The overlay appears and focuses; press again to
   hide (toggle). The tray icon's **Show overlay** does the same; **Quit Cortex** exits.
2. Type a prompt and send. The reply streams in token by token (violet glow while working, the
   design's colour-on-activity), then settles back to the sleek resting state.
3. Confirm follow-ups keep context (the brain persists session state; each turn is a fresh
   `Converse` sharing the app's `session_id`).
4. **The confirm flow** (ADR-0022; needs the email sidecar's write path enabled on the stack:
   `CORTEX_EMAIL_SEND_ENABLED=true` + SMTP credentials, see
   [email-imap.md](email-imap.md)): ask for a send ("email ada a quick hello"). The reply
   pauses on the **approval card** (tool name, the draft as key→value lines, the reason).
   **Approve** → the send runs and the reply reports it sent; **deny** → the reply relays that
   it wasn't sent. Then check fail-closed: trigger another confirm and ignore it (or dismiss to
   the orb). The brain denies on timeout (default 120 s) and the reply says the user declined.
   A confirm arriving while minimized surfaces the preview, which must **not** auto-fade while
   the question is open.

5. **The connection indicator** (ADR-0011 addendum): the header dot is green on summon while the
   brain is up. Stop the brain (`just down`), summon again: it turns red within the retry budget
   and stays red, re-checking every 5 s while the panel is open. Start the brain again and the
   dot goes green on its own, without a re-summon, and the chat list fills in with it. Point
   `CORTEX_BRAIN_ADDR` at a live brain with the **wrong** `CORTEX_SEAM_TOKEN` to see amber
   instead of red: the brain answered `Unauthenticated`, so it is reachable and rejecting the token.

Override the seam address or chord as needed:

```powershell
$env:CORTEX_BRAIN_ADDR = "http://127.0.0.1:50051"
$env:CORTEX_HOTKEY = "ctrl+alt+space"
npm run tauri dev
```

If the brain runs with a seam token (`CORTEX_SEAM_TOKEN` set on the compose stack,
ADR-0016), set the **same** variable for the shell before `tauri dev`. An untokened body
gets `Unauthenticated` on every call:

```powershell
$env:CORTEX_SEAM_TOKEN = "<the same secret the brain serves with>"
```

## Notes

- **What's proven vs. the user's to confirm.** The frontend (prompt → stream → render, the mode
  machine, theming) is browser-validated here and 100%-gated. **Still the user's to confirm on
  Windows:** the `os_windows` `global-hotkey` registration, the tray, window show/hide, the
  real `converse` command streaming a live brain turn to the webview, the `confirm_response`
  command carrying an approval back into the open turn (ADR-0022), and the `check_link` command
  behind the indicator (its classification is gated in `body_core::link` and checked against a
  real brain by the `body-rpc` live suite, so what Windows adds is the IPC hop).
- **What a stalled turn looks like, and when the body gives up on one** (ADR-0024 idle-gap
  addendum). A turn has no time limit: the reply may take as long as the model and its tools take,
  and the thinking indicator stays up while events keep arriving. What is bounded is **silence**.
  If the brain accepts the turn and then sends nothing at all for `CORTEX_BRAIN_TURN_FIRST_GAP_MS`
  (default 600000, ten minutes), or stops sending mid reply for `CORTEX_BRAIN_TURN_IDLE_GAP_MS`
  (default 7200000, two hours), the body stops waiting: the reply settles on whatever text arrived,
  carrying `no reply within …`, and the header dot goes **red** with the same line, because nothing
  answered. That is the same reading a dead brain draws, and it is the correct one: from the body's
  side a brain that has stopped sending and a brain that is gone are indistinguishable. The user
  never has to wait for either bound, since the Stop control ends a turn in place at any time,
  keeping the partial text and recording no error.
  The mid-stream default is long because it has to clear a **delegated subtask**, which may wait an
  hour for the CPU budget and then run for forty minutes without the seam seeing anything. A stack
  composed without the subagent sidecars never produces that silence, so turn it down:
  `CORTEX_BRAIN_TURN_IDLE_GAP_MS=600000` matches the first-event bound and settles a wedged turn in
  ten minutes instead of two hours.
- **v1 window behaviour.** A fixed 640×720 frameless **opaque** always-on-top window; the hotkey
  **toggles** it (no hide-on-blur, so validation is predictable). Deferred to a later overlay-polish
  pass (all together): a **transparent** window so only the panel floats (a first attempt bled
  through the panel content and left a window border; it needs doing properly with click-through),
  **click-through** margins, **hide-on-blur**, and the morph to a real screen-corner orb.
- **CSP** is `null` for v1 (a fully local app loading only bundled assets); tighten it once the IPC
  + dev allow-list is settled on the host.
- **If the hotkey collides** with other software, set a different `CORTEX_HOTKEY`; a registration
  failure is logged (stderr) and non-fatal. The tray still summons the overlay. If `global-hotkey`
  event delivery ever misbehaves, the ADR-0011 fallback is Tauri's `global-shortcut` plugin behind
  the same unchanged `Hotkey` port.
