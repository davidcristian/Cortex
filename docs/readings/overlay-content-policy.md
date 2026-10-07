# Readings: the overlay's content security policy

What Tauri does with the content security policy in `body/app/src-tauri/tauri.conf.json`, and what
the overlay did under it on the Linux shell. Cited by [ADR-0011](../adr/ADR-0011-body-v1.md)
decision 5 and [the overlay design](../design/overlay-ux.md#4-the-interaction-state-machine). The
procedure is the Linux section of the
[overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## What Tauri does with the policy

Read on 2026-10-07 from the source of the versions `Cargo.lock` names: `tauri` 2.11.5,
`tauri-codegen` 2.6.3, `tauri-utils` 2.9.3 and `wry` 0.55.1.

- **Where it applies.** The page runs under the policy only when Tauri serves it from the bundle,
  in a build with the `tauri/custom-protocol` feature, which `tauri build` turns on. Without that
  feature the window loads `devUrl` from Vite and no policy applies (`get_app_url` in
  `tauri/src/manager/mod.rs`), so neither `npm run dev` nor a plain `cargo build` shows a
  violation. `devCsp` replaces `csp` only in a build without that feature that has no `devUrl`.
- **How it is sent.** One code path on every desktop platform, with no `cfg(target_os)` in it:
  `get_asset` computes the policy for each HTML file and `protocol/tauri.rs` sends it as a
  `Content-Security-Policy` response header, which wry hands to WebKitGTK (`set_http_headers`) and
  to WebView2 (`CreateWebResourceResponse`).
- **What it adds.** `set_csp` adds `'self'` and a `sha256` hash of every bundled `.js` file and of
  every inline `<script>` to `script-src`, and a fresh nonce to `style-src` for each `<style>`
  element and to `script-src` for each `script[src^='http']`. The overlay's page has neither kind
  of element, so only `script-src` changes. It adds no origin. The page's own origin,
  `tauri://localhost` on Linux and `http://tauri.localhost` on Windows, is `'self'`; the IPC
  origin, `ipc://localhost` on Linux and macOS and `http://ipc.localhost` on Windows and Android
  (`convertFileSrc` in `scripts/core.js`), must be in the policy itself.
- **A blocked IPC request still works.** `scripts/ipc-protocol.js` sends each command with `fetch`
  to the IPC origin and, on any failure, logs a console warning and sends that command and every
  later one through `window.ipc.postMessage`. A policy without the IPC origin therefore shows only
  as a violation, which is why the run below listens for violations rather than for failures.

## Every surface on the Linux shell

**2026-10-07**, a debug build with `--features tauri/custom-protocol` over a fresh `npm run build`,
WebKitGTK 2.52.6 drawing in software on `Xvfb`, against a stack built from the tree with the
shipped cortex, no projector, `CORTEX_SCHEDULE_BACKEND=redis` and `schedule_task` named in
`CORTEX_TOOLS_GATED`. The test build merged a policy over the config through `TAURI_CONFIG` that
added a local server to `connect-src` and named it in `report-uri`, and the built `index.html` had an
inline script listening for `securitypolicyviolation` that posted each event to that server. Tauri
hashed that script into `script-src`, as above. Every key and click came from `xdotool`.

- **No violation.** Neither the listener nor `report-uri` reported one across: the summon and the
  link probe, a streamed turn and its opened thoughts, a `schedule_task` confirm card left to time
  out and one approved, a picture pasted from the X clipboard and a JPEG dropped from a GTK drag
  source, both drawn as thumbnails, a turn sending both pictures, the reminder card and its
  dismissal, the switcher with `Ctrl+K`, `Ctrl+Up` and `Ctrl+Down`, a rename through the row's form
  and a hoist, the console's Face tab with Midnight, Tangent and Trance picked and its Chords tab,
  and a turn minimized to the orb whose preview counted down and faded.
- **The policy as enforced**, from a violation's `originalPolicy`: the merged policy's directives
  in another order, with two hashes after `script-src 'self'`, the bundle's script and the listener.
- **The listener reports what it should.** A canary image from an outside origin, loaded 4 s after
  the page, was reported by both the event and `report-uri`. A build whose `connect-src` lacked
  `ipc:` and whose `img-src` lacked `data:` reported the first IPC request,
  `ipc://localhost/plugin%3Aevent%7Clisten`, under `connect-src`; a turn then streamed as usual
  over `postMessage`. Its pasted picture drew an empty thumbnail and an `img-src` report naming
  `data`.
- **The committed policy alone**, built with no merge and no listener, opened the panel in the
  stored appearance, drew a pasted picture's thumbnail and sent a turn holding it.

Method: `measurements/overlay-csp-2026-10-07/` (the build and shell scripts, the listener, its
server, both policies, the two violation logs, the event log and the frames in `shots/`).
