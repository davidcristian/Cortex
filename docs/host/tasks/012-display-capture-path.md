# The whole-display GDI capture path

**Status:** never attempted
**Sitting:** windows-capture
**Capability:** W
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The same sentence lives in two places that are still current, and the wording below is
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s 2026-07-18 addendum, its opening paragraph
(the ROADMAP carried it too until that file was slimmed on 2026-07-19):

> the GDI backend is authored, cross-compiled for `x86_64-pc-windows-msvc` and clippy-linted from
> Linux, and **has never captured a real pixel**

[runbooks/vision.md](../../runbooks/vision.md) opens with the same statement, which is the other place
to correct when this check finally runs.

## Why this one is different

Kept verbatim from [refinements/vision.md](../../refinements/index.md#vision), the entry that moved here:

> **Host-side Windows validation of the whole capture path.** The one part of this slice no gate
> can reach, and the only one on the ADR's host-only list without a backlog line until
> 2026-07-19. In order: the real GDI blit of a live desktop; **capturing while the overlay is
> visible, to prove `WDA_EXCLUDEFROMCAPTURE` held**, which is the check nothing else can stand in
> for (if it silently fails, the self-injection loop is live); per-monitor DPI behaviour; the
> body-authored receipt appearing and reading well; GDI's black-rectangle behaviour on
> hardware-overlay and DRM-protected surfaces; and hotkey-to-answer latency with its vision
> surcharge. Runbook: [../runbooks/vision.md](../../runbooks/vision.md).

And from [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s Consequences, which is the fuller
form and adds the prediction and one clause that is **not** host work at all:

> **Host-Windows (host only).** The real GDI blit of a live desktop; `WDA_EXCLUDEFROMCAPTURE`
> verified by capturing while the overlay is visible and confirming it is absent; per-monitor DPI
> behavior; the receipt appearing; GDI's black-rectangle behavior on hardware-overlay and
> DRM-protected surfaces; hotkey-to-answer latency with its vision surcharge (predicted 0.5 to 1 s
> over a text turn, dominated by the second inference pass rather than by the body); and the
> resident VRAM figure with the projector loaded on the 24 GB GPU.

The last clause of that list has no OS-native content, so it was briefly filed as a G item on
2026-07-19 and withdrawn the same day: that figure was measured on the 24 GB card at 16K
with the projector loaded on 2026-06-29 and is [ADR-0004](../../adr/ADR-0004-model-lineup.md)'s
11.3 GB, which ADR-0029's own decision 14 leans on. Read the clause as already satisfied rather
than as work owed. The withdrawal is written up at the end of
[gpu-tier-scale.md](../index.md#gpu-tier-scale).

That ADR also flags, on its assumptions list, that "every Win32 GDI and
`SetWindowDisplayAffinity` behavior claim" is "documentation-derived and user-verifiable only".
This sitting is the only thing that turns those claims into findings.

## Before you start

- `CORTEX_HOST_CAPTURE=1` in the shell's environment. The kill switch fails closed, so without it
  every capture answers `PermissionDenied` and the shell prints `screen capture is off (...)` at
  startup, which is the first thing to check.
- A cortex with its projector loaded, for the end-to-end answer. **Not a 24 GB requirement**,
  corrected 2026-07-19: this step first carried a **W+G** tag, and
  [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) had already measured the cortex fitting an
  8 GB card beside its projector at `--ctx-size 4096 --parallel 1` on 2026-07-17, then driven a
  real vision turn on it. Any card that holds the cortex answers this; the blit and the
  self-exclusion need no model at all and can be checked against any answering brain.
- The full procedure is [runbooks/vision.md](../../runbooks/vision.md), "Host-only half (Windows, a real
  desktop)", four steps.

## Do the self-exclusion first, not last

The runbook lists it third. Do it first anyway. If `WDA_EXCLUDEFROMCAPTURE` silently failed, the
loop it prevents is already live and the rest of the sitting is measuring a system that is already
unsound.

**Do.** Capture while the overlay is visible: ask "what's on my screen?" with the panel open and
prior conversation on it.

**Pass.** The assistant does **not** describe the overlay. Its own prompt, the prior reply, and any
confirm card are absent from the description.

**Fail.** The assistant describes the overlay's contents. That is model output laundered back into
untrusted model input: a line an attacker gets into a rendered reply becomes screen content on the
next capture. There is no partial credit and no workaround short of the kill switch. If this
fails, set `CORTEX_HOST_CAPTURE=0`, stop, and record it before doing anything else.

## The other six observations

| Observation | Pass looks like | Failure looks like |
| --- | --- | --- |
| The real GDI blit | A reply that describes the actual display | An error from the body, or a capture that never returns |
| A failure sentence from real hardware | Added 2026-08-08. Switch capture off and ask again: the reply says **the body refused to capture the screen**, not that it could not be reached. Then shut the lid or detach the display and ask: the reply says **the host is not in a state to capture the screen** | Either sentence starting "could not reach the body", which is the defect the kinded gateway error removed and would mean a status code arriving as something other than what the mapping writes |
| The receipt | An OS notification, "Screen captured", authored by the **body** | The indicator lights and no notification appears, which means the capture failed or was refused; the reply should say so |
| Per-monitor DPI | The captured image matches what is on screen at the scaling in use | A crop, a stretch, or only part of a scaled monitor |
| Protected surfaces | A **black** rectangle where a hardware-overlay or DRM-protected surface was | The same thing, with no error to distinguish it from a dark screen. This is expected behaviour to know rather than a bug to file |
| Latency | Roughly 0.5 to 1 s over a text turn, dominated by the second inference pass | Materially worse, which points at the body rather than the model and is worth a number |

One expectation that is not a failure: small text on a 4K display may be illegible. That is the
slice's headline risk, measured 2026-08-06 and mitigated by default since the same day. A stock
deployment now captures at 2048 px and reads it at `CORTEX_IMAGE_MAX_TOKENS=1024`, which took a
synthetic 4K corpus from 6 to 8 of 47 ground-truth strings to 36 to 38. Type at 15 px on an
unscaled monitor stays unreadable at every budget tried, so expect that and do not file it
([llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md)).

**Why that row needs real hardware and the rest of its work did not.** The status codes and the
sentences they produce were validated on the dev machine on 2026-08-08, end to end across the
language boundary: the real tonic `body_service` served over loopback with `DeniedScreenCapture`,
which is exactly what the host wires when `CORTEX_HOST_CAPTURE` is unset, and the real
`GrpcBodyGateway` read it, so `PermissionDenied` became `REFUSED` became "the body refused to
capture the screen" with nothing faked in between. What that cannot reach is a code no stub emits.
`CaptureError::NoDisplay` and `CaptureError::Backend` come out of GDI itself, so the only way to
see the `FailedPrecondition` and `Internal` rows produced by a real backend rather than by a
constructed error is a Win32 session with a display to lose ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)'s
2026-08-08 addendum). Everything else about the mapping is gated and green in CI.

## What a pass buys

The capture indicator says the assistant **asked** to look at the screen, which is all the seam
proves; the OS receipt is what proves a picture was taken. Both are consent surfaces, and the
argument for shipping capture ungated rests on them plus the self-exclusion. This sitting is what
turns that argument from a design claim into a measured one.

## Record it

A dated addendum to [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md), extending its
"Still host-only" section with what was seen (especially the two self-exclusion results, the
window the walk actually resolved, and the latency number), and a note in
[runbooks/vision.md](../../runbooks/vision.md). If only the display half runs, record that half and
leave the focus-target check alone.

## Trail

- 2026-07-19: Recorded as a backlog entry for the first time, and the refinements index recorded
  that it was opened by the audit of the slice that landed the opaque-turn escalation refusal
  rather than by any new work: ADR-0029's host-only list had named this validation and no backlog
  line carried it. It left the vision area for the host directory the same day, its wording kept
  verbatim, and a dated pointer stub was left in its place at the origin.
- 2026-07-19: Given its own sitting rather than being folded into the Windows desktop one. The old
  host index argued that in two places. Its table row said the capture path needs its own switch,
  its own receipts and its own expectations, and carries what that index called the single
  highest-consequence check in the repo. Its section on splitting by sitting said capture gets its
  own doc despite being W, because its bring-up and its failure mode differ from the rest of the
  Windows work and because this is the check that gets skipped if it is the sixth bullet on a
  tired evening. The sitting doc these two checks were written in opened with three reasons of its
  own, and the one the index did not carry is that its failure modes go unreported rather than being
  obvious.
- 2026-07-19: The refinements index also recorded why this check moved rather than staying in that
  backlog under a tag. The two backlogs hold different kinds of not-done: the design one holds work
  anyone can pick up once a seam or a consumer unblocks it, and its emptiness gates the README,
  which is a dishonest gate if it also waits on the user pressing a hotkey. The same paragraph
  listed this check among the five entries that left that day, under the name "the whole
  screen-capture path on a real desktop".
- 2026-08-07: The host index corrected half of the reasoning behind the withdrawal described
  above. The withdrawal still stood, but for a different reason than the one written here: the
  agent reaches the GPU through Docker and measured the figure in one sitting, so it was never the
  user's work to do, rather than there having been nothing left to find. The 11.3 GB this file
  cites was an `nvidia-smi` total-used reading with the desktop's own floor inside it, taken on a
  different llama.cpp build, and it was an idle reading where the reservation it fed has to cover
  a peak. Re-measured at the shipped tier shape, the cortex is 8400 to 8484 MiB idle and 8573 MiB
  at its peak above a bracketed floor, and `CORTEX_VRAM_CORTEX_GB` is 8.6 rather than 11.3
  ([ADR-0012](../../adr/ADR-0012-resource-governance.md)'s re-measured-reservation addendum). Both
  readings are kept: the section above reads the clause as satisfied by ADR-0004's 11.3 GB, and
  the host index recorded that figure as superseded by the re-measurement.
