# The real Core Audio volume action

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

**What only this proves.** That `WindowsAudioControl`'s narrowly authorized `unsafe` COM path
really drives the endpoint, and that a container reaches the host body through the Windows
firewall. The agent proved the container-to-host dial on 2026-07-08, but against a Linux gRPC
server under WSL2 native dockerd; the Windows crossing is the untested half of ROADMAP assumption
3. Nothing in CI builds this backend at all.

What is written and checked already: the real `WindowsAudioControl` (Core Audio, `cfg(windows)`,
the `windows` crate, with `unsafe` for COM authorized narrowly to `os_windows` by ADR-0023, the one
crate opting out of the workspace `unsafe_code = forbid`), and the Tauri shell's
`body_server::start()` binding `CORTEX_BODY_ADDR` and serving on Tauri's runtime. What is left is
the real "set volume to 30%" on Windows, per
[body-volume.md](../../runbooks/body-volume.md). The dial across the container boundary is done:
on 2026-07-08 the tokened round trip passed from a container and the untokened dial was rejected
([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)).

This item was mistagged as needing a 24 GB card as well, on an older sentence saying the 12B cortex
does not fit 8 GB. That was false: [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) measured
`gemma-4-12b-it-qat-q4_0.gguf` fitting the 8 GB dev GPU beside its projector at
`--ctx-size 4096 --parallel 1` on 2026-07-17 and drove a real vision turn through the shipped
inference adapter on 2026-07-18. The 11.3 GB reservation that sentence leaned on is a 16K-context
figure. What no card can supply is the Win32 desktop the audio backend needs, so the item is **W**,
and one bring-up closes the cortex-driven half with it.

**Do.** [runbooks/body-volume.md](../../runbooks/body-volume.md), "Host-only half (real Core Audio
on Windows)", three numbered steps. Then say or type **"set volume to 30%"**, and **"what's my
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
  the host index lists for that direction: `CORTEX_BODY_ADDR=0.0.0.0:50151`, the brain brought up
  with `-f docker/docker-compose.body.yml`, and a Windows firewall allowance for that port.

## History

- 2026-07-19: moved here from the refinements backlog, where the real Core Audio "set volume to
  30%" check had been a counted entry in the body-gateway area. A dated pointer stays at each
  origin doc so the trail from an ADR through that backlog still resolves.
- 2026-07-19: the session doc put this check and the reminder toast immediately after the bring-up,
  ahead of the confirm card and the three read surfaces, because those two exercise the
  brain-to-body direction and the firewall crossing, so a failure in either explains failures later
  in the session.
