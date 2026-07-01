# Runbook for the overlay + Tauri shell (Slice 8 host half, ADR-0011)

Two ways to run the body overlay: **(A)** in a plain browser against a fake bridge, with no host, no
Tauri, fully CI-gated; and **(B)** the real Tauri app on Windows. Global hotkey, real brain seam.
(A) is what CI and `just check-overlay` exercise; (B) is the host-only half. Tauri is a GUI with a
webview and a real OS event loop, so it is built and validated on the host, never in CI (ADR-0011).

## A. Browser dev (no host, no Tauri)

```bash
cd body/app
npm ci
npm run dev            # vite on http://localhost:5173; the overlay self-summons
```

The page mounts with `DemoBridge` (a canned streamed reply) and dispatches `cortex:activate` once,
so the design is visible immediately. This is the loop for iterating on look/feel
([overlay-ux.md](../design/overlay-ux.md)). The gate is the same code path:

```bash
just check-overlay     # npm ci + tsc --noEmit + Vitest at 100% line+branch
```

## B. The Tauri app on Windows (host validation)

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
   design's colour-on-activity), then settles sleek.
3. Confirm follow-ups keep context (the brain persists session state; each turn is a fresh
   `Converse` sharing the app's `session_id`).

Override the seam address or chord as needed:

```powershell
$env:CORTEX_BRAIN_ADDR = "http://127.0.0.1:50051"
$env:CORTEX_HOTKEY = "ctrl+alt+space"
npm run tauri dev
```

## Notes

- **What's proven vs. the user's to confirm.** The frontend (prompt → stream → render, the mode
  machine, theming) is browser-validated here and 100%-gated. **Still the user's to confirm on
  Windows:** the `os_windows` `global-hotkey` registration, the tray, window show/hide, and the
  real `converse` command streaming a live brain turn to the webview.
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
