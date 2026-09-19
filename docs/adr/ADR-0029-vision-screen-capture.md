# ADR-0029: Vision: screen capture, and pixels as untrusted content

**Status:** Accepted (2026-08-18)

## Context

The cortex answers "what is on my screen?" by reading a capture the body takes, the first host
capability whose return value is a payload rather than a status. Nothing in the brain moved bytes.
[ADR-0013](ADR-0013-untrusted-content.md)'s boundary is a preamble plus a nonce fence around
untrusted text, and no nonce can enclose an image whose instructions the vision tower reads
directly. One capture can show a password manager, a banking tab and a private conversation. The
interface's default receive limit, 4 MiB, is below a worst-case screen. And a capture is in-turn
tool output, so whether pixels survive a model swap had to be decided against the hard rule.

Measured in Docker before deciding: the server reports vision in `GET /props`, a `role: "tool"`
message containing a PNG part is accepted, and a painted injection was transcribed, not obeyed.

## Decision

### 1. A model-initiated built-in tool, not a user attachment

The cortex calls the built-in `capture_screen` (`cortex_core/screen_tool.py`), which calls
`BodyGateway.capture_screen` as the volume tools call theirs, and so gets audit, the dispatch
budget, `RepeatSalience`, taint at arrival, the `ToolActivity` chip, the confirmer as an opt-in and
exclusion from subagents. `build_builtin_tools` adds it only when a body is configured, and the deep
phase gets a built-in set without it, since the probe (decision 13) asks the cortex endpoint and a
model without a projector invents a screen.

### 2. The image travels with the tool result and the tool message; the inference port does not change

`ToolResult` and `Message` have `images: tuple[ImagePart, ...]`; `result_message` copies them onto
the `Role.TOOL` message; `_to_openai_message` emits a content-parts array when images are present
and the byte-identical string otherwise; `InferenceBackend.stream` is unchanged. Bytes travel beside
`content`, which is logged on failure, scanned for URLs and fenced, and on the message because the
loop re-sends its working list every round. `cortex_core/images.py` (which imports no ports) holds
the bounds, the allowed types (PNG, JPEG, WebP), a validating frozen `ImagePart` and `data_uri` over
stdlib `base64`. The core never decodes an image.

### 3. A capture is always UNTRUSTED and always taints the turn

Success returns `Trust.UNTRUSTED` with the bytes; every failure returns `Trust.TRUSTED`,
`is_error=True` and no images, since nothing untrusted arrived and tainting on a dead body would
block tools that need confirmation for nothing. `TaintLedger.observe` runs on the value holding the
pixels, so the image is never in context untainted. Taint blocks tools that need confirmation,
refuses autonomous `schedule_task` creation and routes subagent spawns to the injection-resistant
model ([ADR-0017](ADR-0017-subagent-model-safety.md)). The brain-written replacement text contains
integers only (both sizes and the capture time), never a window title or coordinates.

### 4. A turn-local opaque bit is the deterministic answer to content that cannot be fenced

`TaintLedger.opaque` is set when an UNTRUSTED result contains images. On an opaque turn the URL
guardrail goes strict under the default `redact` policy, because a URL painted into pixels is never
in the untrusted text the default redacts from; `TurnEngine` records nothing to durable memory
whatever `CORTEX_MEMORY_ON_TAINTED` says, because the reply transcribes the screen; `SwapConductor`
refuses an escalation with the fixed `OPAQUE_TURN_NOTE`. `HandoffRecord` stores the bit
([ADR-0030](ADR-0030-brain-handoff.md)) and `EscalationSlot.snapshot` raises on a tail containing an
image, both behind the conductor's refusal.

`SECURITY_PREAMBLE` names an attached image as untrusted data; the sentence documents the boundary
and does not enforce it. The image variant of the injection test
([ADR-0041](ADR-0041-injection-image-variant.md)) found that over pixels the framing works for every
hijack-shaped attack and not for content manipulation (output laundering), the case ADR-0013
hardened. The boundary is taint and the deterministic layers: the confirmation check, the opaque
bit, the memory block and URL redaction.

### 5. The capture tool needs no confirmation, and the consent step lives in the body

`capture_screen` ships without confirmation; `CORTEX_TOOLS_GATED=send_email,capture_screen` is the
opt-in. In place of a confirm card: an OS notification the body shows after every successful
capture, from fixed body strings (display or window, never the window's name; best effort; off with
`CORTEX_HOST_CAPTURE_NOTIFY=0`), a host off switch `CORTEX_HOST_CAPTURE` without which the shell
wires `DeniedScreenCapture`, and the overlay's capture dot (decision 18).

Requiring confirmation is declined: a tool needs confirmation when it is outbound or irreversible,
which a screen read is not; a call needing confirmation on a tainted turn is denied without the
confirmer, so "read this email, then look at my screen" would be impossible; and a card on the main
interaction is confirmation fatigue. The residual risk is same-turn: an injected tool result can
drive a capture in the turn it arrived (measured through the real dispatcher), while outbound tools
stay denied. One laundering attack of ten reaches the reply as formatting, which confirmation would
not stop. Requiring it is a one-line change to `DispatchPolicy.gated_names`.

### 6. Pixels are turn-local, enforced as an invariant

`Message.__post_init__` refuses images on any role but `TOOL`, both `SessionStore`s raise
`SessionStoreError` on an append containing an image (a shared contract check), and retention is
zero. In-turn pixels live in the orchestrator like every in-turn tool message; a swap restores the
question and the reply that describes the screen, and a model can capture again rather than replay a
stale picture. Keeping a picture across a swap would take stored image parts, a content-addressed
store, and a deep tier started with a projector and probed (no brain-tier candidate has one).
Per-source memory rules are declined: the interface sends no source identity by decision (no window
title or application name, and either target can show a password manager). On an opaque turn the
user's own sentence goes unrecorded too; recording that half alone is recorded as a task.

### 7. The body downscales and encodes in pure core; one byte limit, enforced twice

The port returns raw BGRA; pure `body_core` crops (decision 16), downscales the long edge with an
integer box filter, encodes PNG, and over the byte bound halves the edge at most twice before
`TooLarge`. `DEFAULT_MAX_EDGE` is 1600, clamped at 4096. The body's `MAX_CAPTURE_BYTES` and the
brain's `MAX_IMAGE_BYTES` are both 6 MiB, kept equal by the constant registry
([ADR-0042](ADR-0042-cross-tree-constant-registry.md)). The request sends `max_bytes` and
`max_edge`, the body clamps both to its own, and the brain re-checks both after receipt, since an
older body ignores a field it does not know. One gRPC limit changes: `GrpcBodyGateway.connect`
receives up to 16 MiB. 6 MiB is enough for noise at 1600 px and every realistic screen at 2048 px,
and the last halving is a quarter of the requested edge, so `TooLarge` needs a bound under about 450
KB at 2048 px. The policy sits in body core because `cfg(windows)` code cannot be measured by
coverage.

### 8. ScreenCapture is a synchronous Send and Sync trait in its own core submodule

`capture(&self, &CaptureRequest) -> Result<CapturedFrame, CaptureError>`, synchronous as the OS is
(`off_worker` moves it off the async worker). `CapturedFrame` is the display's `RawFrame` plus the
resolved rectangle, and `CaptureError` has five variants: `NoDisplay`, `NoTarget`, `Disabled`,
`Backend`, `TooLarge`. `DeniedScreenCapture` is covered on Linux CI, and the Linux and macOS
backends are coverage-off stubs.

### 9. GDI BitBlt on Windows, with its own unsafe authorization

`BitBlt(SRCCOPY | CAPTUREBLT)` and `GetDIBits`, every GDI object created and released in one call,
under a module-scoped `allow(unsafe_code)` with its own authorization line: no COM apartment and no
persistent device, so it fits `off_worker`'s `FnOnce + Send + 'static` closure. Sizes are physical
pixels because tao's event loop makes the process per-monitor DPI aware before the body server
starts; nothing asserts that, so the DPI host row would show its loss.

### 10. The overlay excludes itself from capture, and fails closed

The shell sets `WDA_EXCLUDEFROMCAPTURE` on the overlay at setup and wires `DeniedScreenCapture` if
that fails, since otherwise text an attacker gets into a reply is read back off the screen.

### 11. Proto fields are added only with a consumer

`CaptureScreenRequest` has `max_edge = 1`, `target = 2`, `max_bytes = 3`; `ImageBlob` has
`source_width = 5`, `source_height = 6`, `captured_at_unix_ms = 7`; `CaptureScreenReply` has
`resolved_target = 2`; `ServerEvent` has `ToolOutcome = 8`. Each was added with the code using it
([ADR-0027](ADR-0027-turn-provenance.md)); `format` and `display_index` wait for that code.

### 12. BodyGateway.capture_screen returns a pure-core value, once, under a deadline

`capture_screen(*, max_edge, max_bytes, target)` returns the frozen `ScreenCapture` of
`cortex_core/body.py`, fails only with `BodyGatewayError`, and is never retried, since a second
attempt photographs a different screen and shows a second notification. Every `BodyService` call has
a deadline, `CORTEX_BODY_CAPTURE_TIMEOUT_S` (10.0) for a capture and `CORTEX_BODY_CALL_TIMEOUT_S`
(5.0) for volume and notify, declared in `cortex_body_client.gateway`, because each call occupies a
host thread and a body that is not running otherwise takes 20 s to fail on connect backoff. A
timeout is classified unreachable; bounding a call does not make it repeatable. `body_rpc` maps
`NoDisplay` and `NoTarget` to `FailedPrecondition`, `Disabled` to `PermissionDenied`, `Backend` to
`Internal` and `TooLarge` to `ResourceExhausted`, never `Unavailable`, which tonic produces for a
channel that never connected.

### 13. Vision is asked of the running server at each use

`VisionProbe.can_see()` (`cortex_core/sighted.py`) never raises and returns no when it cannot tell,
since a wrong yes costs privacy and a wrong no costs a turn. `SightedToolRegistry` hides
`capture_screen` and refuses the call while the answer is no. `PropsVisionProbe` reads `GET /props`
(2 s timeout) wherever the answer is acted on and caches nothing, so the tool follows the projector
across model-host restarts. `CORTEX_VISION=auto|on|off`: `auto` probes, `on` skips the probe, `off`
or no body registers nothing. The projector is the model host's `CORTEX_MODEL_FILE_CORTEX_MMPROJ`
([ADR-0043](ADR-0043-subagent-server-flags.md) names model files); the adapter quotes up to 300
characters of a non-2xx body, so a server without a projector reports its own hint.

### 14. No placer or model-manager change

The placers and scheduler are unchanged. The cortex reservation (8.6 GiB,
[ADR-0012](ADR-0012-resource-governance.md)) is measured with the projector loaded, and decision
17's image budget costs about 4% of it, so it fits.

### 15. The turn engine was split before the feature was added

Context assembly lives in `cortex_core/turn_context.py` behind `TurnCapabilities`, not `engine.py`.

### 16. The capture target

`target` is a closed vocabulary the body resolves, `CAPTURE_TARGET_DISPLAY` (0, the primary display)
or `CAPTURE_TARGET_FOCUS`, named plainly because a model reads them in a schema. Focus is the
topmost capturable window, not the foreground one (the excluded overlay): visible, not minimised,
cloaked or a tool window, not the shell desktop, titled (the length is read, never the title), not
this process. A bare desktop or a window on another monitor is `NoTarget`, never a silent widening.
Body core crops the display frame to the resolved rectangle inside the downscale, so a window within
the edge travels pixel for pixel; `source_width`/`source_height` still describe the display.
`resolved_target` is read off `covers_display()`, so the notification and the model's sentence
follow one test. A missing or unknown `target` is a tool error that never reaches the body, and
`RepeatSalience` compares name and arguments, so each target may be captured twice a loop. A
model-named rectangle is declined: at the engine budget the model invented 38 of 47 answers rather
than decline, so it would name wrong rectangles.

### 17. What the model can read, and what the budget costs

`CORTEX_IMAGE_MAX_TOKENS` emits `--image-max-tokens N` with `--ubatch-size max(N, 512)` when a
projector is loaded, since the budget alone aborts `llama-server` on a large picture. The maintainer
chose budget 1024 with `CORTEX_BODY_CAPTURE_MAX_EDGE` 2048: 36 to 38 of 47 strings off a 4K desktop
against 6 to 8 at the engine budget, for about 400 MiB and 1.6 times the time to first token. The
body's default stays 1600, since a caller naming no edge has a budget the body cannot know. The
window crop reaches 15 px text inside the edge but lowers the whole-desktop reading, so it is not
the default; it turns declines, not inventions, into reads. The tool's description says so, asserted
by `test_the_steer_promises_only_what_the_window_crop_measurement_supports`, and the reply does not
say a window was resampled, since a caption was measured not to change behaviour.

### 18. The capture outcome

`ToolOutcome { tool_name, ok }` follows each dispatch the turn made itself: one bit, the audit
record's result, where `ok = false` means this side cannot say the screen was read. The overlay's
`capture` state moves from `null` to `"asked"` to `"read"` and resets at turn end; a capture shrunk
by halving is read, a refused one stays asked. A delegated step is announced and never settled,
since nothing reads its outcome and subagents cannot capture.

### 19. Thinking stays on for a vision turn

The request sends no `max_tokens` (a 64-token cap returned an empty reply), so a capture turn runs
with thinking on, about five times slower on an invoice screen. Turning it off is a separate
setting.

## Consequences

- **CI covers the path without a GPU or an OS**: every rejection and invariant above, both opaque
  consumers, a capture's taint denying a later call that needs confirmation, and the Rust crop,
  halving and error mapping. Real pixels need the host: [windows-capture](../host/index.md#windows-capture).
- **Accepted risks.** GDI renders hardware-overlay and DRM surfaces black with no error; a capture
  turn pays a second inference pass; a URL the model retypes, defangs or describes passes the
  guardrail, a residual that names no work.
- **Open work** under `docs/refinements/tasks/`: the attachment path, an `AttachmentStore`, a
  picture across a swap, `Windows.Graphics.Capture`, multi-monitor and DPI reporting, JPEG or WebP,
  Linux and macOS backends, pixel screening, a resampled bit, and the user's half of an opaque turn.

## Alternatives rejected

- **The attachment path first** (a second inbound payload, a foreign image decoded in the brain);
  **inline base64 in the session store** (no TTL, re-read every turn, counted as zero characters);
  an `AttachmentStore` now, a `stream` keyword, or a handle attached out of band (taint separated
  from arrival).
- **Bytes in `content`**, a **TRUSTED stamp**, or **the preamble as the boundary**, measured false.
  **A strict guardrail by default** penalises text-only deployments, and choosing strict at the
  composition root when capture is on states the policy twice.
- **A synthetic user message** containing the image forges a user turn (the fallback if a template
  rejects a tool-role parts array). **An MCP sidecar tool** would reach subagents. **DXGI or
  Windows.Graphics.Capture** (a persistent device, COM, async frames), **encoding in `os_windows`**,
  **decoding in the brain**, **hide, capture, show** (flicker and races).
- **A startup-only probe or a residency signal**: a swap restarts the tier from the same argv, so a
  signal arrives on the wrong event. **`VisionGatedToolRegistry` as a name**: that word means a tool
  needing confirmation.

## Related

- Code: `cortex_core/{screen_tool,images,sighted,body}.py`, `cortex_orchestrator/vision.py`, the
  `screen*.rs` files of body core, rpc and `os_windows`, and the overlay's `CaptureDot.tsx`.
- Runbooks [vision](../runbooks/vision.md), [llamacpp-gpu](../runbooks/llamacpp-gpu.md); modules
  [brain-core](../modules/brain-core.md), [brain-orchestrator](../modules/brain-orchestrator.md),
  [brain-body-client](../modules/brain-body-client.md), [body-core](../modules/body-core.md);
  measurements [vision-capture](../readings/vision-capture.md),
  [injection-over-pixels](../readings/injection-over-pixels.md).
- [ADR-0019](ADR-0019-tainted-memory-recording.md), [ADR-0023](ADR-0023-body-gateway-volume.md),
  [ADR-0030](ADR-0030-brain-handoff.md), [ADR-0041](ADR-0041-injection-image-variant.md).
