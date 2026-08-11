# The real Core Audio volume action

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

**What only this proves.** That `WindowsAudioControl`'s narrowly authorized `unsafe` COM path
actually drives the endpoint, and that a container reaches the host body **through the Windows
firewall**. The agent proved the container to host dial on 2026-07-08, but against a Linux gRPC
server under WSL2 native dockerd; the Windows crossing is the untested half of ROADMAP assumption
3. Nothing in CI builds this backend at all.

The two paragraphs below were the ROADMAP's status for this work. They were **preserved here when
the ROADMAP was slimmed on 2026-07-19** and are no longer in that file, so this doc is their only
home; the live statement of the same obligation is
[ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)'s "Host-Windows (host-only)" paragraph and its
2026-07-08 addendum ("Remaining for the slice: only the **Host-Windows** half").

> **Host-authored (host-validated on Windows, never in CI).** The real `WindowsAudioControl`
> (Core Audio, `cfg(windows)`, the `windows` crate; `unsafe` for COM authorized narrowly to
> `os_windows` by ADR-0023, the one crate opting out of the workspace `unsafe_code = forbid`), and
> the Tauri shell's `body_server::start()` binding `CORTEX_BODY_ADDR` and serving on Tauri's
> runtime.

> **Remaining:** only the **Host-Windows** real Core Audio validation ("set volume to 30%"), per
> [body-volume.md](../../runbooks/body-volume.md). The **agent-Docker** dial across the container
> boundary is done (2026-07-08, [ADR-0023 addendum](../../adr/ADR-0023-body-gateway-volume.md)): the
> tokened round-trip passed from a container and the untokened dial was rejected. On an 8 GB GPU
> the gemma-4-12B cortex does not fit, so a fully *cortex-driven* `set_volume` is bounded by what
> fits; the seam + gateway + tool path validated directly.

**That last sentence is stale, and this item was mistagged for it (corrected 2026-07-19).** It
first read as needing a 24 GB card for the cortex-driven half, which would have made this item
**W+G**. The VRAM clause is false: [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) measured
the real `gemma-4-12b-it-qat-q4_0.gguf` fitting the 8 GB dev GPU **beside its projector** at
`--ctx-size 4096 --parallel 1` on 2026-07-17 and drove a real vision turn through the shipped
inference adapter on 2026-07-18. The 11.3 GB reservation the sentence leaned on is a 16K-context
figure. What no card can supply is the Win32 desktop the audio backend needs, so the whole item is
**W**, and one bring-up closes the cortex-driven half with it. (Second correction, 2026-07-19:
this paragraph also cited a cortex-driven tool call "here on 2026-07-03", which was agent-run on
the 24 GB card, the machine the agent had then. The dev-card evidence is the vision turn.)

**Do.** [runbooks/body-volume.md](../../runbooks/body-volume.md), "Host-only half (real Core Audio on
Windows)", three numbered steps. Then say or type **"set volume to 30%"**, and **"what's my
volume?"** for `get_volume`.

**Pass.** Host output volume moves. No approval card appears, because volume is ungated by design
(reversible). `get_volume` answers with the real level.

**Fail, and what each failure means.**
- `UNAUTHENTICATED: invalid or missing seam token`: the shell and the brain disagree on
  `CORTEX_SEAM_TOKEN`.
- The assistant says it could not reach the body: the dial failed. Either the firewall blocked the
  port or `CORTEX_BODY_ADDR` bound loopback only. A dead body is a recoverable `is_error` by
  design, so this fails as an honest sentence rather than a crash.
- The tool never fires: the cortex did not emit it. Not a body failure.
- The call succeeds and nothing moves: this is the interesting failure, and it is the COM path.

**Record it.** A dated addendum to [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md), whose
2026-07-16 addendum on moving the sync OS calls off the async worker ends its "Validated" paragraph
with "Unchanged and still host-side: the real 'set volume to 30%' on Windows" (later addenda follow
it, so search for the sentence rather than reading the file's end); a note in
[runbooks/body-volume.md](../../runbooks/body-volume.md); then delete this section.

## Notes

- The sitting doc numbers this check **1**, and it says the numbering of the checks is deliberately
  untouched because ADRs cite them by number.
- This is one of the two checks the brain dials the body for, so it needs the extra prerequisites
  the host index lists for that direction: `CORTEX_BODY_ADDR=0.0.0.0:50151`, the brain brought up
  with `-f docker/docker-compose.body.yml`, and a Windows firewall allowance for that port.
- The host index's roll call adds that this check is blocked on nothing but the sitting, and that
  it closes the fully cortex-driven `set_volume` with it.

## Trail

- 2026-07-19: arrived in the host directory from the refinements backlog, where the real Core Audio
  "set volume to 30%" check had been a counted entry in the body-gateway area. The refinements index
  recorded it as one of five counted entries and two uncounted residuals that left for
  [docs/host/](../index.md) that day, wording kept verbatim, with a dated pointer stub staying at
  each origin doc so the trail from an ADR through that backlog still resolves.
- 2026-07-19: the sitting doc gave an order for the checks and put this one and the reminder toast
  immediately after the bring-up, ahead of the confirm card and then the three read surfaces,
  because those two exercise the brain to body direction and the firewall crossing, so a failure in
  either explains failures later in the sitting.
