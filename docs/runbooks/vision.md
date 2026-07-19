# Runbook: vision (the assistant looks at your screen)

The vision slice (ADR-0029) gives the cortex eyes: a model-initiated `capture_screen` built-in
takes a picture of the primary display over the existing brain→body seam, and the picture rides
the tool result into the next inference round. The CI-gated half is green under `just check` on
Linux with fakes. This runbook covers the two halves a gate cannot see: the agent-runnable
Docker half (the projector, the probe, and a real image through the real inference adapter), and
the host-only Windows half (a real GDI blit of a real desktop).

**Nothing in this file has been run against a real screen.** The GDI backend is authored,
cross-compiled for `x86_64-pc-windows-msvc`, and clippy-linted; it has never captured a pixel.

## The switches, end to end

Three independent things must all be true before a capture can happen. That is deliberate: each
one fails closed on its own.

| Switch | Side | Default | What it decides |
| --- | --- | --- | --- |
| `CORTEX_HOST_CAPTURE=1` | host (Tauri shell) | off | Whether the body wires the real GDI backend at all. Anything else serves `DeniedScreenCapture`, which answers `PermissionDenied`. |
| overlay self-exclusion | host (automatic) | required | The shell calls `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` on the overlay at setup. If it fails, capture stays off even with the switch on. |
| `CORTEX_VISION` | brain | `auto` | Whether `capture_screen` is advertised to the model. `auto` probes `GET {CORTEX_INFERENCE_ENDPOINT}/props` once at startup; `on`/`off` fix the answer. |

Plus the model itself: `CORTEX_MMPROJ_FILE_CORTEX` names the multimodal projector the model host
loads beside the cortex tier. Without it the server reports no vision, the probe says no, and
the tool is never advertised.

The other knobs, all optional:

| Variable | Side | Default | Meaning |
| --- | --- | --- | --- |
| `CORTEX_HOST_CAPTURE_NOTIFY` | host | on | `0` silences the body-authored OS notification a successful capture shows. |
| `CORTEX_BODY_CAPTURE_MAX_EDGE` | brain | `0` | Longest edge to ask the body for, in physical pixels, **and** the edge the reply is held to on receipt. `0` leaves the body's own default (1600) and holds the reply to the 8192 px domain ceiling alone. Outside `0..8192` the brain refuses to boot. |
| `CORTEX_BODY_MAX_IMAGE_BYTES` | brain | `6291456` | The byte budget, sent to the body **and** re-verified on receipt. 6 MiB, the same number as the body's own `MAX_CAPTURE_BYTES`. It may only tighten: outside `1..6291456` the brain refuses to boot, since the body clamps to its own ceiling anyway. |
| `CORTEX_BODY_CAPTURE_TIMEOUT_S` | brain | `10.0` | The deadline on the capture call, the only one on this seam. Must be positive. |
| `CORTEX_TOOLS_GATED` | brain | `escalate_to_brain,send_email` | Adding `capture_screen` here puts an approval card in front of every capture. See "if you want it gated" below. |

## Agent half (Docker, a real projector and a real image)

1. Name the projector beside the model, in the repo-root `.env`:
   ```
   CORTEX_MMPROJ_FILE_CORTEX=google/gemma-4-12B-it-qat-q4_0-gguf/mmproj-gemma-4-12b-it-qat-q4_0.gguf
   ```
   It ships under the same read-only models mount, so no extra bind is needed.
2. `just up-gpu`, then confirm the server reports the capability:
   ```
   curl -s http://127.0.0.1:8080/props | jq .modalities
   ```
   `{"vision": true, ...}` is what the brain's probe reads. A `false` here means the argv did
   not get the `--mmproj` pair; check `docker compose logs model-host` for the child's flags.
3. The brain's startup log carries the probe's own answer (`vision probe answered`, with the
   endpoint and the verdict). A failure logs `vision probe failed` and counts as no vision, so
   the tool is simply not advertised.

**What the projector costs.** ADR-0004's 11.3 GB cortex reservation is a **with-mmproj**
measurement, so enabling it spends budget the placer has been charging since before it loaded;
subagent headroom is unchanged. An image costs 266 prompt tokens at any size from 720p up.

## Host-only half (Windows, a real desktop)

What this closes, what a pass and a failure look like for each observation, and where to record
them: [docs/host/windows-capture.md](../host/windows-capture.md).

1. Build and run the Tauri app on Windows with the switch on:
   ```
   set CORTEX_HOST_CAPTURE=1
   npm run tauri dev
   ```
   The shell prints `screen capture is off (...)` when either condition failed, which is the
   first thing to check if every capture answers `PermissionDenied`.
2. Ask the assistant "what's on my screen?". Expect, in order: the tool chip, the overlay's
   capture indicator lighting for the rest of the turn (its label says the assistant *asked* to
   look, which is all the seam proves; the OS receipt is what proves a picture was taken), the OS
   notification ("Screen captured"), and a reply describing the display. If the indicator lights
   and no notification appears, the capture failed or was refused, and the reply should say so.
3. **Verify the self-exclusion**, which is the one check that cannot be inferred: capture while
   the overlay is visible and confirm the assistant does **not** describe the overlay. If it
   does, the exclusion silently failed and the loop it prevents is live (a line an attacker gets
   into a rendered reply becomes screen content on the next capture).
4. Things to expect rather than debug: GDI renders hardware-overlay and DRM-protected surfaces
   (some video players, some browsers' protected playback) **black**, silently, with no error to
   distinguish it from a dark screen. Small text on a 4K display downscaled to 1600 px may be
   illegible; that is the headline risk, and the first mitigation is llama.cpp's
   `--image-max-tokens` rather than a bigger PNG.

## What a capture does to the turn

Worth knowing before the first surprise, because it is all deliberate:

- The turn becomes **tainted**, so every gated tool (`send_email`, `escalate_to_brain`) is
  hard-denied for the rest of it, with no confirmation offered. "Read this email, then look at
  my screen, then mail me a summary" will refuse the last step. Ask again in a fresh message.
- **What taint does not close is the capture itself.** `capture_screen` is ungated, and the taint
  gate closes only gated tools, so an injected tool result can drive a capture **in the same turn
  it arrived in**, with the injection live in the context that decides to capture. That is the
  deliberate consequence of shipping ungated, and it is the paragraph to weigh before overruling
  it below. What still holds on that turn: every outbound gated tool is denied, URL redaction goes
  strict, and nothing reaches durable memory.
- The turn becomes **opaque**, which additionally: escalates the output guardrail to strict
  redaction (every URL the user did not send is removed from the reply), blocks the exchange
  from durable memory whatever `CORTEX_MEMORY_ON_TAINTED` says, and refuses a deep-model
  handoff outright: the swap conductor ends the turn with a note saying so, since a picture cannot
  be handed to the deep model and no brain-tier model could read one anyway.
- **Nothing is retained.** The picture dies with the turn: no session store, no handoff record,
  no memory. A reopened chat shows the reply and no evidence of what was seen, and the audit
  line records dimensions, a byte count and a timestamp only. A later dispute about what a
  capture contained genuinely cannot be answered from the store.
- At most **two** captures per turn, for free: the tool takes no arguments, so every call is
  identical and the existing repeat bound applies.

## If you want it gated

`capture_screen` ships ungated. Turning that around is one env var and no code:

```
CORTEX_TOOLS_GATED=escalate_to_brain,send_email,capture_screen
CORTEX_TOOLS_GATE_REASONS__capture_screen=the assistant will take a picture of your whole screen
```

Know what it buys and costs. It buys an approval before every screen read. It costs the flagship
interaction an approval card that cannot say what will be captured (the call takes no
arguments), and it makes "read this email, then look at my screen" structurally impossible,
because a gated call on a tainted turn is denied outright and a first capture then self-denies a
second. The receipt and the kill switch are the chosen mitigation instead.

## Turning it off

Any one of these is enough, and each is honest about which layer it turns off:

- `CORTEX_HOST_CAPTURE` unset: the body refuses every capture, whatever the brain thinks.
- `CORTEX_VISION=off`: the tool is never advertised, so the model cannot ask.
- `CORTEX_MMPROJ_FILE_CORTEX` unset: the model has no eyes, and `auto` discovers that itself.
