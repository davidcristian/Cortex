# The screen-capture sitting (tag W)

One check with six observations inside it, in its own doc for three reasons: it has a different
bring-up from the rest of the Windows work (a host kill switch, a receipt, its own env), its
failure modes are **silent** rather than loud, and it carries the one observation nothing else in
this repo can stand in for.

**Status: never attempted.** The backend has never captured a real pixel.

The same sentence lives in two places that are still current, and the wording below is
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md)'s 2026-07-18 addendum, its opening paragraph
(the ROADMAP carried it too until that file was slimmed on 2026-07-19):

> the GDI backend is authored, cross-compiled for `x86_64-pc-windows-msvc` and clippy-linted from
> Linux, and **has never captured a real pixel**

[runbooks/vision.md](../runbooks/vision.md) opens with the same statement, which is the other place
to correct when this check finally runs.

## Why this one is different

Kept verbatim from [refinements/vision.md](../refinements/vision.md), the entry that moved here:

> **Host-side Windows validation of the whole capture path.** The one part of this slice no gate
> can reach, and the only one on the ADR's host-only list without a backlog line until
> 2026-07-19. In order: the real GDI blit of a live desktop; **capturing while the overlay is
> visible, to prove `WDA_EXCLUDEFROMCAPTURE` held**, which is the check nothing else can stand in
> for (if it silently fails, the self-injection loop is live); per-monitor DPI behaviour; the
> body-authored receipt appearing and reading well; GDI's black-rectangle behaviour on
> hardware-overlay and DRM-protected surfaces; and hotkey-to-answer latency with its vision
> surcharge. Runbook: [../runbooks/vision.md](../runbooks/vision.md).

And from [ADR-0029](../adr/ADR-0029-vision-screen-capture.md)'s Consequences, which is the fuller
form and adds the prediction and one clause that is **not** host work at all:

> **Host-Windows (host only).** The real GDI blit of a live desktop; `WDA_EXCLUDEFROMCAPTURE`
> verified by capturing while the overlay is visible and confirming it is absent; per-monitor DPI
> behavior; the receipt appearing; GDI's black-rectangle behavior on hardware-overlay and
> DRM-protected surfaces; hotkey-to-answer latency with its vision surcharge (predicted 0.5 to 1 s
> over a text turn, dominated by the second inference pass rather than by the body); and the
> resident VRAM figure with the projector loaded on the 24 GB GPU.

The last clause of that list has no OS-native content, so it was briefly filed as a G item on
2026-07-19 and withdrawn the same day: that figure was measured on the 24 GB card at 16K
with the projector loaded on 2026-06-29 and is [ADR-0004](../adr/ADR-0004-model-lineup.md)'s
11.3 GB, which ADR-0029's own decision 14 leans on. Read the clause as already satisfied rather
than as work owed. The withdrawal is written up at the end of
[gpu-tier-scale.md](gpu-tier-scale.md).

That ADR also flags, on its assumptions list, that "every Win32 GDI and
`SetWindowDisplayAffinity` behavior claim" is "documentation-derived and user-verifiable only".
This sitting is the only thing that turns those claims into findings.

## Before you start

- `CORTEX_HOST_CAPTURE=1` in the shell's environment. The kill switch fails closed, so without it
  every capture answers `PermissionDenied` and the shell prints `screen capture is off (...)` at
  startup, which is the first thing to check.
- A cortex with its projector loaded, for the end-to-end answer. **Not a 24 GB requirement**,
  corrected 2026-07-19: this step first carried a **W+G** tag, and
  [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) had already measured the cortex fitting an
  8 GB card beside its projector at `--ctx-size 4096 --parallel 1` on 2026-07-17, then driven a
  real vision turn on it. Any card that holds the cortex answers this; the blit and the
  self-exclusion need no model at all and can be checked against any answering brain.
- The full procedure is [runbooks/vision.md](../runbooks/vision.md), "Host-only half (Windows, a real
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

## The other five observations

| Observation | Pass looks like | Failure looks like |
| --- | --- | --- |
| The real GDI blit | A reply that describes the actual display | An error from the body, or a capture that never returns |
| The receipt | An OS notification, "Screen captured", authored by the **body** | The indicator lights and no notification appears, which means the capture failed or was refused; the reply should say so |
| Per-monitor DPI | The captured image matches what is on screen at the scaling in use | A crop, a stretch, or only part of a scaled monitor |
| Protected surfaces | A **black** rectangle where a hardware-overlay or DRM-protected surface was | The same thing, silently, with no error to distinguish it from a dark screen. This is expected behaviour to know rather than a bug to file |
| Latency | Roughly 0.5 to 1 s over a text turn, dominated by the second inference pass | Materially worse, which points at the body rather than the model and is worth a number |

One expectation that is not a failure: small text on a 4K display may be illegible. That is the
slice's headline risk, measured 2026-08-06 and mitigated by default since the same day. A stock
deployment now captures at 2048 px and reads it at `CORTEX_IMAGE_MAX_TOKENS=1024`, which took a
synthetic 4K corpus from 6 to 8 of 47 ground-truth strings to 36 to 38. Type at 15 px on an
unscaled monitor stays unreadable at every budget tried, so expect that and do not file it
([llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)).

## What a pass buys

The capture indicator says the assistant **asked** to look at the screen, which is all the seam
proves; the OS receipt is what proves a picture was taken. Both are consent surfaces, and the
argument for shipping capture ungated rests on them plus the self-exclusion. This sitting is what
turns that argument from a design claim into a measured one.

## Record it

A dated addendum to [ADR-0029](../adr/ADR-0029-vision-screen-capture.md), extending its
"Still host-only" section with what was seen (especially the self-exclusion result and the
latency number), and a note in [runbooks/vision.md](../runbooks/vision.md). Then delete this doc
and its row in [index.md](index.md).
