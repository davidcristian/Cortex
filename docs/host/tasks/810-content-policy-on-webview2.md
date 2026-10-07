# The overlay's content security policy on WebView2

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-07

The shell's page runs under the content security policy in `body/app/src-tauri/tauri.conf.json`
([ADR-0011](../../adr/ADR-0011-body-v1.md) decision 5). On the Linux shell every overlay surface ran
under it with no violation, and Tauri 2.11's source sends the same header through the same code on
Windows, adding only script hashes. The policy names WebView2's IPC origin, `http://ipc.localhost`,
itself, and the page's origin, `http://tauri.localhost`, is `'self'`
([readings](../../readings/overlay-content-policy.md)).

**What only this proves.** That WebView2 enforces the policy as WebKitGTK did: Tauri's own scripts
run, IPC requests reach `http://ipc.localhost` rather than falling back to `postMessage`, and a
picture pasted or dropped from Windows draws its `data:` thumbnail.

**Do.** A `tauri dev` run loads Vite with no policy and shows nothing, so build the page into the
shell: `npm run build` in `body/app`, then `cargo build --features tauri/custom-protocol` in
`body/app/src-tauri`, and run `target\debug\cortex-body.exe` with the brain up. Open the developer
tools from the page's context menu and keep the console in view. Summon, send a turn and open its
thoughts, ask for a reminder in one minute with `schedule_task` named in `CORTEX_TOOLS_GATED` and
approve the card, paste a screenshot (Win+Shift+S then Ctrl+V), drop a JPEG from Explorer, send
both, open the switcher with `Ctrl+K`, open the console's Face and Chords tabs, and minimize a
streaming turn to the orb with Escape until its preview fades.

**Pass.** Every surface works, and the console shows no `Content Security Policy` message and no
`IPC custom protocol failed` warning.

**Fail.** A violation names the directive and the blocked address. When the overlay needs that
source, add it to that directive in `tauri.conf.json` and to
`body/app/src/bridge/contentPolicy.test.ts`, and correct decision 5 and the readings. A missing IPC
origin does not break anything visible; only the console warning shows it.

**Record it.** Edit [ADR-0011](../../adr/ADR-0011-body-v1.md) in place where the consequences name
this as host work, then close this file.

## History

- 2026-10-07: Filed when the policy replaced `null` in the shell's config, split from
  [H-014](014-os-window-polish.md), whose fourth part this was, so that the window polish keeps
  its three parts and this check stands alone.
