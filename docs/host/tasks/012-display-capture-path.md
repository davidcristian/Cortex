# The whole-display GDI capture path

**Status:** never attempted
**Session:** windows-capture
**Capability:** W
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The GDI backend is written, cross-compiled for `x86_64-pc-windows-msvc` and clippy-linted from
Linux, and **has never captured a real pixel**.
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) records that, and
[runbooks/vision.md](../../runbooks/vision.md) opens with the same statement, which is the other
place to correct when this check runs. ADR-0029 also flagged, on its assumptions list, that every
Win32 GDI and `SetWindowDisplayAffinity` behaviour claim is derived from documentation and can only
be verified by the user. This session is what turns those claims into findings.

## Why this one is different

No automated check can reach any of it. In order: the real GDI blit of a live desktop; **capturing
while the overlay is visible, to prove `WDA_EXCLUDEFROMCAPTURE` held**, which is the check nothing
else can stand in for, because if it silently fails the self-injection loop is live; per-monitor DPI
behaviour; the body-authored receipt appearing and reading well; GDI's black-rectangle behaviour on
hardware-overlay and DRM-protected surfaces; and hotkey-to-answer latency with its vision surcharge,
predicted at 0.5 to 1 s over a text turn and dominated by the second inference pass rather than by
the body.

ADR-0029's host-only list also named the resident VRAM figure with the projector loaded on the
24 GB GPU. That clause has no OS-native content and was withdrawn on 2026-07-19: the figure was
measured on the 24 GB card at 16K with the projector loaded on 2026-06-29 and is
[ADR-0004](../../adr/ADR-0004-model-lineup.md)'s 11.3 GB. The reservation is 8.6 GiB since the
projector was measured again in place ([ADR-0012](../../adr/ADR-0012-resource-governance.md)).

## Before you start

- `CORTEX_HOST_CAPTURE=1` in the shell's environment. The kill switch fails closed, so without it
  every capture answers `PermissionDenied` and the shell prints `screen capture is off (...)` at
  startup, which is the first thing to check.
- A cortex with its projector loaded, for the end-to-end answer. **Not a 24 GB requirement**,
  corrected 2026-07-19: ADR-0029 measured the cortex fitting an 8 GB card beside its projector at
  `--ctx-size 4096 --parallel 1` on 2026-07-17, then drove a real vision turn on it. Any card that
  holds the cortex answers this; the blit and the self-exclusion need no model at all.
- The full procedure is [runbooks/vision.md](../../runbooks/vision.md), "Host-only half (Windows, a
  real desktop)", four steps.

## Do the self-exclusion first, not last

The runbook lists it third. Do it first anyway. If `WDA_EXCLUDEFROMCAPTURE` silently failed, the
loop it prevents is already live and the rest of the session is measuring a system that is already
unsound.

**Do.** Capture while the overlay is visible: ask "what's on my screen?" with the panel open and
prior conversation on it.

**Pass.** The assistant does **not** describe the overlay. Its own prompt, the prior reply, and any
confirm card are absent from the description.

**Fail.** The assistant describes the overlay's contents. That is model output fed back into
untrusted model input: a line an attacker gets into a rendered reply becomes screen content on the
next capture. There is no partial credit and no workaround short of the kill switch. If this fails,
set `CORTEX_HOST_CAPTURE=0`, stop, and record it before doing anything else.

## The other six observations

| Observation | Pass looks like | Failure looks like |
| --- | --- | --- |
| The real GDI blit | A reply that describes the actual display | An error from the body, or a capture that never returns |
| A failure sentence from real hardware | Added 2026-08-08. Switch capture off and ask again: the reply says **the body refused to capture the screen**, not that it could not be reached. Then shut the lid or detach the display and ask: the reply says **the host is not in a state to capture the screen** | Either sentence starting "could not reach the body", which is the defect the kinded gateway error removed and would mean a status code arriving as something other than what the mapping writes |
| The receipt | An OS notification, "Screen captured", written by the **body** | The indicator lights and no notification appears, which means the capture failed or was refused; the reply should say so |
| Per-monitor DPI | The captured image matches what is on screen at the scaling in use | A crop, a stretch, or only part of a scaled monitor |
| Protected surfaces | A **black** rectangle where a hardware-overlay or DRM-protected surface was | The same thing, with no error to distinguish it from a dark screen. This is expected behaviour to know rather than a bug to file |
| Latency | Roughly 0.5 to 1 s over a text turn, dominated by the second inference pass | Materially worse, which points at the body rather than the model and is worth a number |

One expectation that is not a failure: small text on a 4K display may be illegible. That is the
slice's headline risk, measured 2026-08-06 and reduced by default since the same day. A stock
deployment now captures at 2048 px and reads it at `CORTEX_IMAGE_MAX_TOKENS=1024`, which took a
synthetic 4K corpus from 6 to 8 of 47 ground-truth strings to 36 to 38. Type at 15 px on an
unscaled monitor stays unreadable at every budget tried, so expect that and do not file it
([llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md)).

**Why that failure-sentence row needs real hardware and the rest of its work did not.** The status
codes and the sentences they produce were validated on the dev machine on 2026-08-08, end to end
across the language boundary: the real tonic `body_service` served over loopback with
`DeniedScreenCapture`, which is what the host wires when `CORTEX_HOST_CAPTURE` is unset, and the
real `GrpcBodyGateway` read it, so `PermissionDenied` became `REFUSED` became "the body refused to
capture the screen" with nothing faked in between. What that cannot reach is a code no stub emits.
`CaptureError::NoDisplay` and `CaptureError::Backend` come out of GDI itself, so the only way to see
the `FailedPrecondition` and `Internal` rows produced by a real backend is a Win32 session with a
display to lose ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md) decision 10).

## What a pass buys

The capture indicator says the assistant **asked** to look at the screen; the OS receipt is what
proves a picture was taken. Both are consent surfaces, and the argument for shipping capture without
an approval step rests on them plus the self-exclusion. This session is what turns that argument
from a design claim into a measured one.

## Record it

What was seen goes in the readings record under [docs/readings/](../../readings/README.md) that
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) rests on (especially the two self-exclusion
results, the window the walk resolved, and the latency number), that ADR is edited in place so its
host-only list no longer names what ran, and a note goes in
[runbooks/vision.md](../../runbooks/vision.md). If only the display half runs, record that half and
leave the focus-target check alone.

## History

- 2026-07-19: recorded as a backlog entry for the first time. ADR-0029's host-only list had named
  this validation and no backlog line covered it. It moved from the vision area to the host
  directory the same day, with a dated pointer left at the origin.
- 2026-07-19: given its own session rather than being folded into the Windows desktop one, because
  its bring-up and its failure mode differ from the rest of the Windows work, because its failure
  modes go unreported rather than being obvious, and because this is the check that gets skipped if
  it is the sixth bullet on a tired evening.
- 2026-08-07: the host index corrected half of the reasoning behind the withdrawal described above.
  The withdrawal still stood, but for a different reason: the agent reaches the GPU through Docker
  and measured the figure in one run, so it was never the user's work to do. The 11.3 GB cited here
  was an `nvidia-smi` total-used reading with the desktop's own floor inside it, taken on a
  different llama.cpp build, and it was an idle reading where the reservation it fed has to cover a
  peak. Measured again at the shipped tier shape, the cortex is 8400 to 8484 MiB idle and 8573 MiB
  at its peak, and `CORTEX_VRAM_CORTEX_GB` is 8.6 rather than 11.3
  ([ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 14).
