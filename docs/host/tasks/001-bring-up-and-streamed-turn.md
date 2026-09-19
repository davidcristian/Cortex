# The bring-up: hotkey, tray, and a streamed turn

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

**What only this proves.** That `os_windows` really registers a system-wide hotkey on a live Win32
desktop, that the tray item and window show and hide work, and that the `converse` Tauri command
streams a live brain turn into the webview across the real IPC hop. Everything under that is
already covered by tests: the chord parser is pure and 100% covered in `body_core`, and the
overlay's streaming reducer is covered in `body/app`. What no test reaches is a real registration
against a real desktop that other software is competing for.

[ADR-0011](../../adr/ADR-0011-body-v1.md)'s host-only consequence names the `os_windows`
`global-hotkey` registration, the tray and window show and hide, and the real `converse` command
streaming a live brain turn to the webview, as two of its six lines. Neither had an item here until
2026-07-19. It reads as obvious work for the reason it went missing: it is what you do before the
checks, so nobody wrote it down as one.

**The bring-up, once, for all seven checks.** Prerequisites are in [index.md](../index.md). Then:

```powershell
$env:CORTEX_SEAM_TOKEN = "<the same secret the brain serves with>"
$env:CORTEX_BODY_ADDR  = "0.0.0.0:50151"
cd body\app
npm run tauri dev
```

with the brain up beside it. Add `-f docker/docker-compose.body.yml` to the compose command so the
brain can dial back (`CORTEX_BODY_BACKEND=grpc`), and `-f docker/docker-compose.gpu.yml` for the
real cortex. Full procedure: [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B.

**Do.** [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B, validation steps 1 to
3. Press **Ctrl+Alt+Space** from some other foreground application; press it again to hide. Use the
tray's **Show overlay**. Type a prompt, watch the reply stream, then send a follow-up that depends
on the first (the session is shared across turns).

**Pass.** The overlay appears from any foreground app and toggles away again; the tray item does
the same; a typed turn streams token by token rather than arriving whole, and a follow-up keeps
context.

**Fail, and what each failure means.**

- The hotkey never fires: something else owns the chord. It is configurable (`CORTEX_HOTKEY`,
  default `ctrl+alt+space`, parsed by `body/app/src-tauri/src/hotkey.rs`, which falls back to the
  default and prints on an unparseable value), so try another chord before calling it a defect.
- The overlay appears but no text arrives: the body/brain connection, not the desktop.
  `UNAUTHENTICATED` means the shell and the brain disagree on `CORTEX_SEAM_TOKEN`; a red connection
  dot means the brain is not reachable at `CORTEX_BRAIN_ADDR`.
- The whole reply arrives at once: the stream is being buffered somewhere, which is a finding about
  the IPC hop rather than about the brain, since the brain's deltas are covered on both sides.

**Record it.** Edit [ADR-0011](../../adr/ADR-0011-body-v1.md) in place where the run changes the two
lines named above, and put any figure the run took in its readings record under
[docs/readings/](../../readings/README.md); then delete this section.

## Notes

- The session doc numbers this check **0**, because it is the bring-up itself and every other check
  depends on it. It was added on 2026-07-19 and the numbering of the rest is deliberately
  unchanged, since ADRs cite these checks by number.
- The bring-up commands above are the session's shared bring-up, kept here because this check is
  that bring-up. Every other check in the session starts from the same block.

## History

- 2026-07-19: the way this check went missing became a practice recorded in the host index. Reading
  an origin ADR's user list against the item list is the cheap way to catch a host line with no
  item behind it, and it is worth doing whenever an ADR gains a host line.
