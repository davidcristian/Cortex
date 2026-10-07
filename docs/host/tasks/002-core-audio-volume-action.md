# The real Core Audio volume action

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Verified:** 2026-10-07

**What only this proves.** That `WindowsAudioControl`'s narrowly authorized `unsafe` COM path
really drives the endpoint, and that a container reaches the host body through the Windows
firewall. Everything above the OS call ran on the Linux shell on 2026-10-07: the cortex emitting
`set_volume` and `get_volume` from spoken-style requests, no approval card, the brain dialing the
shell's `BodyService` from a container, and `LinuxAudioControl` moving a real PulseAudio sink
([readings](../../readings/body-actions-linux.md#volume)). The tokened container-to-host dial
passed on 2026-07-08 against a Linux gRPC server
([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)), so the Windows crossing is the untested
half of ROADMAP assumption 3. CI runs clippy on `os_windows` for the `x86_64-pc-windows-msvc`
target (`just check-body`), which type-checks this backend but never links or runs it.

What is written and checked already: the real `WindowsAudioControl` (Core Audio, `cfg(windows)`,
the `windows` crate, with `unsafe` for COM authorized narrowly to `os_windows` by ADR-0023, the one
crate opting out of the workspace `unsafe_code = forbid`), and the Tauri shell's
`body_server::start()` binding `CORTEX_BODY_ADDR` and serving on Tauri's runtime. What is left is
the real "set volume to 30%" on Windows, per [body-volume.md](../../runbooks/body-volume.md). It
needs a Windows desktop and any GPU that holds the cortex
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) measured the 12B cortex on an 8 GB card).

**Do.** [runbooks/body-volume.md](../../runbooks/body-volume.md), "The Windows check, with real
Core Audio", three numbered steps. Then say or type **"set volume to 30%"**, and **"what's my
volume?"** for `get_volume`.

**Pass.** Host output volume moves. No approval card appears, because volume needs no approval by
design (it is reversible). `get_volume` answers with the real level.

**Fail, and what each failure means.**

- `UNAUTHENTICATED: invalid or missing token`: the shell and the brain disagree on
  `CORTEX_SEAM_TOKEN`.
- The assistant says it could not reach the body: the dial failed. Either the firewall blocked the
  port or `CORTEX_BODY_ADDR` bound loopback only. A dead body is a recoverable `is_error` by
  design, so this fails as a plain sentence rather than a crash.
- The tool never fires: the cortex did not emit it. Not a body failure.
- The call succeeds and nothing moves: this is the interesting failure, and it is the COM path.

**Record it.** Edit [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md) in place so it no longer
lists the real "set volume to 30%" on Windows as host-side, put any figure the run took in its
readings record under [docs/readings/](../../readings/README.md), and add a note in
[runbooks/body-volume.md](../../runbooks/body-volume.md); then delete this section.

## Notes

- The session doc numbers this check **1**, and the numbering is deliberately unchanged because
  ADRs cite the checks by number.
- This is one of the two checks the brain dials the body for, so it needs the extra prerequisites
  the host index lists for that direction: `CORTEX_BODY_ADDR=0.0.0.0:23151`, the brain brought up
  with `-f docker/docker-compose.body.yml`, and a Windows firewall allowance for that port.

## History

- 2026-07-19: moved here from the refinements backlog, where the real Core Audio "set volume to
  30%" check had been a counted entry in the body-gateway area. A dated pointer stays at each
  origin doc so the trail from an ADR through that backlog still resolves.
- 2026-07-19: the session doc put this check and the reminder toast immediately after the bring-up,
  ahead of the confirm card and the three read surfaces, because those two exercise the
  brain-to-body direction and the firewall crossing, so a failure in either explains failures later
  in the session.
- 2026-10-07: corrected the claim that nothing in CI builds this backend, and ran the
  cortex-driven half on the Linux shell against the cortex on the card: "set volume to 30%",
  "what's my volume?", mute, unmute and a typed "set volume to 55%" each called the right tool,
  sent no approval card, and moved the sink `pactl` read back
  ([readings](../../readings/body-actions-linux.md#volume)). This narrows the item to Core Audio
  and the Windows firewall.
