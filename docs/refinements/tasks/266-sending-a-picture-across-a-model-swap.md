# Sending a picture across a model swap

**Status:** open, needs a port change first
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** A turn that read the screen has to reach the deep model rather than end on the
ask-again note. The work then starts with R-257's store, a brain-tier
projector setting, and a probe of that tier.

Nothing persists an in-turn image: not the session store, and not the handoff record. The record's
codec lists message fields by name, so a `Message.images` would be dropped without error, which is
why `EscalationSlot.snapshot` raises on a tail message containing one before any record exists. The
user-visible consequence is live: a turn that looked at the screen cannot hand over to the deep
model at all, and the conductor ends it with a note telling the user to ask again in a fresh
message.

The expensive half is the pixels themselves, which needs the `AttachmentStore` in
[257](257-content-addressed-attachment-store.md) and a deep tier that can read one. That capability
is a wiring gap rather than a missing file: the model host names a projector for the cortex tier
alone (`cortex_mmproj_file`, used by `_vision()` in
`brain/packages/model_manager/src/cortex_model_manager/config.py`), and the brain tier's `extra`
has its prompt-cache size and its reasoning budget and no projector, so a deep tier started today
is text-only whatever sits beside its GGUF. A deep tier started with one would still not be asked:
the vision probe (`PropsVisionProbe`, built by `build_vision` in the orchestrator's `vision.py`)
reads `/props` from the cortex's `inference.endpoint` alone, and the deep tier answers at
`CORTEX_BRAIN_ENDPOINT`.

The cheap half was done 2026-08-03 ([ADR-0030](../../adr/ADR-0030-brain-handoff.md)).
`HandoffRecord` gained `opaque: bool` beside `tainted`, `EscalationSlot.snapshot` reads it off the
live ledger, `taint_ledger()` rebuilds it, the Redis codec writes and reads the key strictly (a
missing one is a corrupt record, like every other taint field), and the `HandoffStore` contract
suite gained a round trip for both values that the fake and the Redis adapter both pass. Before
that, `taint_ledger()` rebuilt the bit as `False`, which was sound only because no opaque turn can
reach a record, since the conductor refuses first.

What the bit buys is that neither consumer can be handed a manufactured `False` the day the picture
half relaxes that refusal, since a defaulted bit and a real one look identical to both of them. The
codec's treatment of an unknown field was checked rather than assumed: `decode_record` reads keys
by name, so an unknown key is ignored without error while a missing known key raises into
`HandoffStoreError`, which is why the bit is written and read rather than defaulted. Proven by
mutation three ways in the codec (drop the encode line and thirteen store tests fail; default it on
read with `.get` and only the strict-decode test fails; drop both and the contract round trip fails
on `loaded == record`) and two ways in the core (drop it from `snapshot` or from `taint_ledger()`
and the two new brain-phase tests fail, each with a tainted-but-not-opaque control so the measured
difference is the bit and not the taint). Observed live against the compose Redis rather than
fakeredis alone: `"opaque": true` and `"opaque": false` in the stored document, both read back
exactly on the record and on the ledger rebuilt from it.

## History

- 2026-07-19: Written down here, having been missed when the slice closed, and named in ADR-0029's
  Deferred paragraph. It is what the fix to the opaque-turn escalation refusal opened.
- 2026-08-03: The cheap half was done and the expensive half stayed open. Unusually for this
  backlog, the entry was right about itself on every checkable claim, including its cost.
- 2026-08-03: Recorded why the distinction between a live refusal and a correct schema is drawn so
  hard here: the last refusal in this area shipped inside a tool behind confirmation where it could
  never fire, with a test that reached the branch by calling `invoke` directly, which is why the
  conductor test now asserts the store saw no write at all.
- 2026-08-03: The bit's two consumers, which this entry's text left unnamed, are strict URL
  redaction and the durable-memory block, and both are reached by the deep phase.
- 2026-09-13: Checked and left open, with the capability claim corrected. The entry said no
  brain-tier candidate on the mount has a projector, and that is no longer true: the 31B QAT pick
  ships `gemma-4-31B-it-mmproj.gguf` beside its GGUF, and the Qwen 27B and 35B-A3B candidates each
  ship an `mmproj` file. What keeps a replayed picture unreadable is that the model host has no
  setting to give the deep tier one. Nothing in the brain declares an `AttachmentStore`, no store
  persists pixels, and `SwapConductor._prepare` still refuses an opaque turn on
  `slot.refs.taint.opaque` before the store is touched.
- 2026-09-19: Checked against the handoff code, with two stale claims fixed, one defence named, a
  third prerequisite added and the trigger restated. `SwapConductor._prepare` returns
  `OPAQUE_TURN_NOTE` on `slot.refs.taint.opaque` before the unhosted-tier check and before the
  store is read, and the one change to the deep phase since (a handoff cut mid tool call now ends
  rather than fails) does not reach it. The codec still writes a message field by field with no
  `images` key, but this file left out that `EscalationSlot.snapshot` raises on an image in the
  tail, which it has done since 2026-07-18, so a relaxed refusal would fail loudly rather than drop
  a picture. The sentence saying `HandoffRecord` lacks the bit has been false since the cheap half
  was done and is gone. The brain tier's `extra` gained its prompt-cache size and still has no
  projector. The added prerequisite is the probe: `build_vision` points it at the cortex's
  inference endpoint, and nothing asks the deep endpoint whether it reads pictures. The old trigger
  was this entry's own prerequisites, one of which waits for a consumer that is this entry, so each
  waited on the other; the trigger now names the demand.
