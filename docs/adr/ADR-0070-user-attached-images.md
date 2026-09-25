# ADR-0070: Images the user attaches to a turn

**Status:** Accepted (2026-09-25)

## Context

`UserTurn.images` has been in [proto/body.proto](../../proto/body.proto) since the first gRPC slice
and nothing read it. Vision arrived the other way: the model calls `capture_screen`, the body
returns a picture, and the picture enters the context on a `Role.TOOL` message
([ADR-0029](ADR-0029-vision-screen-capture.md)). An image the user attaches differs from a capture
in four ways. It travels from the body to the brain inside the `Converse` stream rather than as the
answer to a brain call. It is subject to the brain server's transport limit rather than the
`GrpcBodyGateway` client's. It is a file from anywhere rather than a frame the body encoded
itself. And it belongs to the user's own message, which the security preamble names as
authoritative.

Three layers assert that pixels are turn-local: `Message.__post_init__` refuses images on any role
but `TOOL`, `EscalationSlot.snapshot` refuses a handoff tail that has one, and both
`SessionStore`s refuse to append one (`store_codec.refuse_images` for Redis). This record states
where an attachment lives, how it marks the turn, what the brain accepts, and which of those layers
relaxes.

## Decision

### 1. Pixels live for the turn in the orchestrator, and history keeps a note

The engine persists the user's message as the typed text followed by a brain-written note, for
example `(Attached to this message and not kept: image/png 1600x900.)`, and never the pixels. The
pixels go on the turn's in-memory copy of that message, in the working list the tool loop sends to
the model on every inference round.

The hard rule in [ADR-0001](ADR-0001-architecture.md) is about the model server: nothing may live
in its process or its KV cache. The working list is sent whole with every request, so a cortex
that is reloaded mid-turn receives the pictures again on the next round, exactly as a capture's
tool message is. The one place a picture would have to leave the orchestrator is a deep handoff,
and decision 3 refuses that. Storing the pixels in Redis for the turn would therefore keep them
for no reader: the deep tier is started without a projector (ADR-0029 decision 6), so it could not
read them. A later turn sees the note, and the user attaches the picture again to ask about it
again.

### 2. An attachment is untrusted and opaque, following ADR-0013 and ADR-0029

A picture the user chose can still show text they did not write: a screenshot of an email, a photo
of a sign. [ADR-0013](ADR-0013-untrusted-content.md) marks taint by where content came from rather
than by who sent it, and no fence can bracket pixels, so `TaintLedger.observe_attachment()` sets
both `tainted` and `opaque` before the turn assembles its context. Everything those bits already
do applies unchanged: the full tool-shaped security preamble, the confirmation rule for outbound
tools, strict URL redaction on an opaque turn ([ADR-0015](ADR-0015-output-guardrail.md)), no
durable memory whatever `CORTEX_MEMORY_ON_TAINTED` says, and no escalation.

The framing is scoped to the turn. The security preamble names images on tool results only, and it
is a measured prompt, so it is not changed. Instead the working copy of the user's message ends
with `ATTACHMENT_FRAME`, a sentence saying the pictures below are attached and that text drawn in a
picture is content to describe, never an instruction. Only a turn with an attachment sends it. Its
effect on the real cortex is not measured yet; the deterministic boundary is the taint above.

### 3. A turn with an attachment does not hand over to the deep model

`SwapConductor` already refuses an escalation from an opaque turn with `OPAQUE_TURN_NOTE`, before
anything is drained or unloaded, and the confirmation rule denies `escalate_to_brain` on a tainted
turn before that. The note now says "This turn holds a picture" rather than naming the screen,
since it covers both sources. The user asks again in a new message without the picture.

### 4. Limits, and what a refused attachment returns

- **Count.** At most `MAX_ATTACHED_IMAGES` (4) per turn. Four is a reading of "a few pictures",
  not a measured bound; the live check filed with this record measures what four cost the cortex.
- **Each image.** The existing `ImagePart` checks: PNG, JPEG or WebP, at most `MAX_IMAGE_BYTES`
  (6 MiB), width and height declared and each in 1 to 8192. The body's capture uses the same
  6 MiB cap.
- **Type.** The first bytes must be the signature of the declared type (`signature_matches`: the
  PNG signature, the JPEG start-of-image marker, or `RIFF` with `WEBP` at offset 8).
- **Transport.** The brain's gRPC server accepts messages up to `MAX_TURN_MESSAGE_BYTES`, four
  images at their cap plus 1 MiB. gRPC's default of 4 MiB would refuse one full-size image at the
  transport with `RESOURCE_EXHAUSTED`, which the body reports as a transport failure rather than a
  refusal.
- **Refusal.** An attachment that fails any check ends the stream with
  `SeamError{code: "attachment_refused", message}` before the turn starts, so nothing is stored.
  The message names the attachment by its 1-based position and the check it failed. The body maps
  it to `TurnEvent::Failed` like every other `SeamError`. No proto message is added: the error
  code is a string, as the other three codes are.

### 5. The body decodes; the brain checks and never decodes

The brain reads `ImageBlob` into `ImagePart` in the orchestrator (`cortex_orchestrator/attached.py`)
and checks it in the pure core (`cortex_core/attachments.py`), which reads bytes already in memory
and does no I/O. Neither decodes pixels: llama.cpp's projector does, as it does for a capture. The
body is where a user's file is opened, decoded, downscaled to the capture path's default long edge
of 1600 px and encoded again as PNG or JPEG, so the width and height the brain receives are the
body's own reading of pixels it produced. That keeps an arbitrary file's parser out of the brain
container and gives the model the same resolution a capture has.

### 6. One of the three layers relaxes

- `Message.__post_init__` accepts images on `USER` as well as `TOOL`. `ASSISTANT` and `SYSTEM`
  still raise. The inference adapter sends a content-parts array for any message with images, so
  a user message is no longer the case the old rule protected against.
- `EscalationSlot.snapshot` is unchanged. The user's message is in the working list's base, not in
  the tail the snapshot serializes, and the conductor refuses an opaque turn first.
- Both `SessionStore`s are unchanged: they still refuse any message with images. The engine
  appends the note-bearing text, so a store never sees pixels.

## Consequences

- `TurnRunner.handle_turn` takes `images: tuple[ImagePart, ...] = ()`. `TurnEngine` and
  `EscalatingTurnEngine` pass it through; a runner that never receives one behaves as before.
- A user message with images and a user message without them are two different requests on the
  wire: the first is a content-parts array, the second the plain string it always was.
- An attachment sent to a cortex without a projector fails the turn as `inference_failed` after
  the note is stored. Refusing it up front needs the vision probe in the turn and is filed as a
  task.
- Memory, titles and the history recap read the stored text, so they see the note and never the
  pixels.

## Alternatives rejected

- **Pixels in Redis for the turn, removed at its end.** No reader: the deep tier cannot see, and
  the cortex already receives them on every round.
- **A bounded image store across turns.** It turns an ongoing record of the user's pictures into
  durable state, with retention, deletion and a second codec, to answer a question the user can ask
  again by attaching the picture again.
- **Trusting an attachment because the user sent it.** The preamble would then tell the model to
  obey any text in a screenshot.
- **Decoding in the brain.** It adds an image parser for arbitrary files to the container that
  holds the conversation, and the body already owns an encoder.

## Related

[ADR-0029](ADR-0029-vision-screen-capture.md) (captures and the opaque bit),
[ADR-0013](ADR-0013-untrusted-content.md) (taint), [ADR-0030](ADR-0030-brain-handoff.md) (the
handoff record), [runbooks/vision.md](../runbooks/vision.md),
[modules/brain-core.md](../modules/brain-core.md),
[modules/brain-orchestrator.md](../modules/brain-orchestrator.md).
