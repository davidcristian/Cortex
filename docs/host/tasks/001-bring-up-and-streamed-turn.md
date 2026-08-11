# The bring-up: hotkey, tray, and a streamed turn

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

**What only this proves.** That `os_windows` really registers a system-wide hotkey on a live Win32
desktop, that the tray item and window show/hide work, and that the `converse` Tauri command
streams a live brain turn into the webview across the real IPC hop. Everything under it is gated:
the chord parser is pure and 100% covered in `body_core`, and the overlay's streaming reducer is
covered in `body/app`. What no gate reaches is a real registration against a real desktop that
other software is also competing for.

**Why it is a numbered check and not just a heading.**
[ADR-0011](../../adr/ADR-0011-body-v1.md)'s Host-Windows addendum names "the `os_windows`
`global-hotkey` registration, the tray, and window show/hide" and "the real `converse` command
streaming a live brain turn to the webview" as two of its six lines, and until 2026-07-19 neither
had a check here. [AGENTS.md](../../../AGENTS.md)'s three-records rule held forward from every item in
this directory and failed backward from that ADR. This is the fix, and the reason it reads as
obvious work is the reason it went missing: it is what you do before the checks, so nobody wrote
it down as one.

**The bring-up, once, for all seven.** Prerequisites are in [index.md](../index.md). Then:

```powershell
$env:CORTEX_SEAM_TOKEN = "<the same secret the brain serves with>"
$env:CORTEX_BODY_ADDR  = "0.0.0.0:50151"
cd body\app
npm run tauri dev
```

with the brain up beside it. Add `-f docker/docker-compose.body.yml` to the compose command so the
brain can dial back (`CORTEX_BODY_BACKEND=grpc`), and `-f docker/docker-compose.gpu.yml` for the
real cortex. Full procedure: [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B.

**Do.** [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B, validation steps 1 to 3.
Press **Ctrl+Alt+Space** from some other foreground application; press it again to hide. Use the
tray's **Show overlay**. Type a prompt, watch the reply stream, then send a follow-up that depends
on the first (the session is shared across turns).

**Pass.** The overlay appears from any foreground app and toggles away again; the tray item does
the same; a typed turn streams token by token rather than arriving whole, and a follow-up keeps
context.

**Fail, and what each failure means.**
- The hotkey never fires: something else owns the chord. It is configurable (`CORTEX_HOTKEY`,
  default `ctrl+alt+space`, parsed by `body/app/src-tauri/src/hotkey.rs`, which falls back to the
  default and prints on an unparseable value), so try another chord before calling it a defect.
- The overlay appears but no text arrives: the seam, not the desktop. `UNAUTHENTICATED` means the
  shell and the brain disagree on `CORTEX_SEAM_TOKEN`; a red connection dot means the brain is not
  reachable at `CORTEX_BRAIN_ADDR`.
- The whole reply arrives at once: the stream is being buffered somewhere, which is a finding about
  the IPC hop rather than about the brain, since the brain's deltas are gated on both sides.

**Record it.** A dated addendum to [ADR-0011](../../adr/ADR-0011-body-v1.md) against the two lines
named above; then delete this section.

## Notes

- The sitting doc numbers this check **0**, because it is the bring-up itself and every other check
  rides on it. It was added on 2026-07-19 and the numbering of the rest is deliberately untouched,
  since ADRs cite these checks by number.
- The bring-up commands above are the sitting's shared bring-up, kept here because this check is
  that bring-up. Every other check in the sitting starts from the same block.
- The host index's roll call adds that this check is done first by construction, and that it closes
  the two ADR-0011 user lines that had no home until 2026-07-19.

## Trail

- 2026-07-19: the host index drew a standing practice out of the way this check went missing.
  Reading an origin ADR's user list against the roll call is the cheap way to catch a host line that
  has no item behind it, and the index recorded that it is worth doing whenever an ADR gains a host
  line.
