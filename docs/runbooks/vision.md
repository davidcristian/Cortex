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
| `CORTEX_VISION` | brain | `auto` | Whether `capture_screen` is advertised to the model. `auto` probes `GET {CORTEX_INFERENCE_ENDPOINT}/props` **on every advertisement and every call**; `on`/`off` fix the answer without touching the network. |

Plus the model itself: `CORTEX_MMPROJ_FILE_CORTEX` names the multimodal projector the model host
loads beside the cortex tier. Without it the server reports no vision, the probe says no, and
the tool is never advertised.

**Changing the projector needs no brain restart, in either direction.** Recreate the `model-host`
service with the variable set or cleared and the next turn follows it: the capability appears when
a projector is loaded beside the model and disappears when one stops being. This is worth knowing
because it used to be the opposite, and the failure was silent and expensive. Measured 2026-08-06:
with the answer taken once at startup, a projector-less recreate left the tool advertised, and the
next "look at my screen" blitted a display, showed the user the capture notification, tainted the
turn, and then died on `image input is not supported - hint: ... you may need to provide the
mmproj`. To watch either direction happen:

```
CORTEX_MMPROJ_FILE_CORTEX= docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml up -d --no-deps --force-recreate model-host
# wait for the tier to reload, then:
curl -s http://127.0.0.1:8080/props | jq .modalities   # {"vision": false, ...}
```

The brain's own log then says `vision probe answered` with `vision: false` on the next turn, and
the tool is gone from that turn's advertisement. Drop the `CORTEX_MMPROJ_FILE_CORTEX=` prefix and
repeat to put it back.

The other knobs, all optional:

| Variable | Side | Default | Meaning |
| --- | --- | --- | --- |
| `CORTEX_HOST_CAPTURE_NOTIFY` | host | on | `0` silences the body-authored OS notification a successful capture shows. |
| `CORTEX_BODY_CAPTURE_MAX_EDGE` | brain | `2048` | Longest edge to ask the body for, in physical pixels, **and** the edge the reply is held to on receipt. `2048` is the brain half of the pair that makes a 4K screen legible, and it is only worth its extra pixels because `CORTEX_IMAGE_MAX_TOKENS=1024` on the model host gives the encoder somewhere to put them ([llamacpp-gpu.md](llamacpp-gpu.md)); lower it and the other one together. `0` hands the edge back to the body's own default (1600) and holds the reply to the 8192 px domain ceiling alone. Outside `0..8192` the brain refuses to boot. |
| `CORTEX_BODY_MAX_IMAGE_BYTES` | brain | `6291456` | The byte budget, sent to the body **and** re-verified on receipt. 6 MiB, the same number as the body's own `MAX_CAPTURE_BYTES`, which `just check-crosscheck` holds it to. It may only tighten: outside `1..6291456` the brain refuses to boot, since the body clamps to its own ceiling anyway. |
| `CORTEX_BODY_CAPTURE_TIMEOUT_S` | brain | `10.0` | The deadline on the capture call, the only one on this seam. Must be positive. |
| `CORTEX_TOOLS_GATED` | brain | `escalate_to_brain,send_email` | Adding `capture_screen` here puts an approval card in front of every capture. See "if you want it gated" below. |

## What the body can be pointed at

`CaptureScreenRequest.target` names one of two things, and the body honours it as of the same
commit that declared the field: `CAPTURE_TARGET_DISPLAY` (zero, the whole primary display, which
is what every capture has always been) and `CAPTURE_TARGET_FOCUS` (the window the user is
looking at). There is no rectangle to name and there will not be one until something can hand
the model a coordinate frame; the body resolves the target itself, because only it knows where
windows are.

**The model is the one who chooses**, as of 2026-08-10. `capture_screen` takes one required
argument, `target`, whose two values are `focus` and `display`, and the tool description tells the
model which to reach for: the window when the question is about one thing in front of the user,
the display when it is about the screen as a whole. There is no default. A call that names no
target, or names one outside the two, comes back as a tool error and takes no picture, which is
also what keeps the repeat bound honest (below).

Two things to know about the focused window:

- It is **not** the foreground window. The user summons the overlay with the hotkey and types the
  question into it, so the overlay is the foreground window at the moment a capture runs, and it
  hides itself from capture. The body walks the desktop's Z-order from the front instead and
  takes the first window that is visible, not minimized, not DWM-cloaked, not a tool window (the
  taskbar is one), not the shell's desktop, titled, not the body's own, and not excluded from
  capture.
- A bare desktop is an **error**, not a whole-screen capture. The body answers
  `FAILED_PRECONDITION`, which the brain reads as "the host is not in a state to capture the
  screen". Falling back to the display would send more of the screen than was asked for with
  neither the model nor the OS receipt knowing.

The receipt says which happened, in the body's own words: "A picture of your screen was sent to
the assistant." or "A picture of one window was sent to the assistant." It is chosen by what
actually crossed the seam, so a maximised window that fills the display reports a screen
capture, and neither sentence ever names the window, a title being attacker-chosen text.

The reply tells the brain the same thing, picked by the same rule, which is why the model is
never told a crop was a shrunk screen. A window capture reads to the model as "screen capture of
one window, cropped out of the 2560x1440 primary display", followed by the fact it can act on:
the rest of the screen was not captured, so it can ask again for the display. Like the receipt,
that sentence names no window title and no coordinates.

**The overlay's capture ring does not distinguish the two.** It says "The assistant looked at
your screen during this reply" for a window read as well, deliberately: a window is part of the
screen, so the coarser sentence is true, and over-reporting is the direction a privacy indicator
should fail in.

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
3. The brain logs the probe's own answer (`vision probe answered`, with the endpoint and the
   verdict) each time it asks, which is once when a turn lists its tools and once more when the
   model actually calls the screen. There is no longer a boot-time line: the first one appears on
   the first turn. A failure logs `vision probe failed` and counts as no vision, so the tool is
   simply not advertised and any capture already in flight is refused.
4. To check what a **forgotten projector** looks like, which is the failure the inference
   adapter's bounded error excerpt exists for, start a second server on the same weights with the
   cortex tier's flags minus the `--mmproj` pair and run the canary against it:
   ```
   docker run -d --name cortex-nommproj --gpus all -p 127.0.0.1:8085:8085 \
     -v "$CORTEX_MODELS_DIR:/models:ro" ghcr.io/ggml-org/llama.cpp:server-cuda \
     --model /models/google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf \
     --host 0.0.0.0 --port 8085 -ngl 99 --ctx-size 16384 --parallel 1 --jinja
   cd brain && uv run pytest -m integration --no-cov \
     packages/inference/tests/test_backend_live.py -k projector
   ```
   It asserts the 500 and llama.cpp's own `mmproj` hint, measured verbatim in ADR-0029's
   2026-08-03 addendum. A red run means the wording moved; re-measure and record the new string.

**What the projector costs.** The cortex reservation has always been a **with-mmproj** figure, so
enabling the projector spends budget the placer was already charging and subagent headroom is
unchanged. It is 8.6 GiB since 2026-08-07, re-measured with the projector loaded at the shipped
16K shape, where the tier peaks at 8573 MiB above the idle floor
([ADR-0012](../adr/ADR-0012-resource-governance.md) re-measured-reservation addendum); the 11.3 GB
this paragraph used to name was ADR-0004's, read as `nvidia-smi` total used with the desktop's own
floor inside it. An image costs 266 prompt tokens at any size from 720p up when the
budget is left to the model, and 1010 at the shipped `CORTEX_IMAGE_MAX_TOKENS=1024` with the
shipped 2048 px capture, for about 400 MiB more VRAM.

**What a picture costs in time.** The cortex thinks before it answers, and on an open-ended ask a
picture makes that near-certain (measured 2026-08-03: 10 of 10 image runs of "what is on my
screen?" thought, against 2 of 5 on the same scaffold with the picture removed). The reply then
begins around 6 s in on a simple screen and 15 s in on one packed with small text, against 0.4 s
pixel-less. Nothing is truncated by it, because the shipped
request sends no `max_tokens` and the server runs at `n_predict: -1`, so this is a latency cost and
not a correctness one. Turning thinking off is a server-side decision the cortex tier does not
take today; it starts the reply in about 1.2 s when it is taken.

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
   capture ring lighting for the rest of the turn, the ring growing its pupil a moment later,
   the OS notification ("Screen captured"), and a reply describing the display. The pupil is the
   dispatch's own outcome coming back: without it the ring's label reads "asked to look", with
   it "looked". A ring that stays open all turn means the capture never reached the model (the
   switch off, the exclusion failed, an unreachable body, or a gated capture declined), and the
   reply should say so. The ring never goes the other way, so an open ring is not proof the
   display was untouched: a capture that failed after the shutter fired looks the same from the
   brain's side, and the OS receipt is the surface that settles that case.
3. **Verify the self-exclusion**, which is the one check that cannot be inferred: capture while
   the overlay is visible and confirm the assistant does **not** describe the overlay. If it
   does, the exclusion silently failed and the loop it prevents is live (a line an attacker gets
   into a rendered reply becomes screen content on the next capture).
4. Things to expect rather than debug: GDI renders hardware-overlay and DRM-protected surfaces
   (some video players, some browsers' protected playback) **black**, silently, with no error to
   distinguish it from a dark screen. Small text on a 4K display is the other one. Downscaled to
   1600 px and read at the model's own image budget it **is** illegible, measured 2026-08-06: 6 to
   8 of 47 ground-truth strings read off five 4K desktops, with the model inventing the rest rather
   than declining. A pair of settings takes that to 36 to 38, `CORTEX_IMAGE_MAX_TOKENS=1024` on the
   model host and `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` here, and **both are the default now**; a
   bigger PNG alone changes nothing. What they cost and the type sizes they still cannot reach (15
   px on an unscaled monitor is unreadable at every budget tried) are in
   [llamacpp-gpu.md](llamacpp-gpu.md).

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
- At most **two** captures per target and **four** per turn. Repeat detection keys on the tool
  name plus its arguments, so each target is its own identity and the old free bound of two
  doubled when the tool gained one. It is four rather than six because a call naming no target is
  refused before the body is reached, and four rather than unbounded because the two spellings
  are matched exactly, `Display` being refused rather than accepted beside `display`.

## If you want it gated

`capture_screen` ships ungated. Turning that around is one env var and no code:

```
CORTEX_TOOLS_GATED=escalate_to_brain,send_email,capture_screen
CORTEX_TOOLS_GATE_REASONS__capture_screen=the assistant will take a picture of your whole screen
```

Know what it buys and costs. It buys an approval before every screen read, and since 2026-08-10
that approval can say something: the call carries a target, so a card could promise "the window
you are looking at" rather than only "a picture". What it still costs is the interaction: it makes
"read this email, then look at my screen" structurally impossible, because a gated call on a
tainted turn is denied outright and a first capture then self-denies a second, and it adds a card
to the flagship gesture. The receipt and the kill switch are the chosen mitigation instead.

## Turning it off

Any one of these is enough, and each is honest about which layer it turns off:

- `CORTEX_HOST_CAPTURE` unset: the body refuses every capture, whatever the brain thinks.
- `CORTEX_VISION=off`: the tool is never advertised, so the model cannot ask.
- `CORTEX_MMPROJ_FILE_CORTEX` unset: the model has no eyes, and `auto` discovers that itself.
