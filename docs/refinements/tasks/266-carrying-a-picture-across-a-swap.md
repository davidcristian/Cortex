# Carrying a picture across a model swap

**Status:** open, a seam or port change comes first
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** A turn that read the screen has to reach the deep model rather than end on the
ask-again note. The work then starts with R-257's store, a brain-tier projector setting, and a
probe of that tier.

Carrying a picture, or at least the `opaque` bit, across a model swap. Named in ADR-0029's own
Deferred paragraph and written down here on 2026-07-19, having been missed when the slice closed.
Nothing persists an in-turn image: no session store, and no handoff record either. The record's
codec enumerates message fields by name, so a `Message.images` would be dropped without error,
which is why `EscalationSlot.snapshot` raises on a tail message carrying one before any record
exists. The **user-visible** consequence is live: a turn that looked at the screen cannot hand over
to the deep model at all, and the conductor ends it with a note telling the user to ask again in a
fresh message. `HandoffRecord` did not carry the `opaque` bit either, so `taint_ledger()` rebuilt
it at `False`; that was sound only because no opaque turn can reach a record (the conductor rejects
first), and carrying the bit as defence in depth was the cheap half of this entry, landed below.
The expensive half is pixels themselves, which wants R-257's `AttachmentStore` and a deep tier
that can read one. The capability half of that is a wiring gap rather than a mount gap: the model
host names a projector for the cortex tier alone (`cortex_mmproj_file`, spent by `_vision()` in
`brain/packages/model_manager/src/cortex_model_manager/config.py`), and the brain tier's `extra`
carries its prompt-cache size and its reasoning budget and no projector, so a deep tier started
today is text-only whatever sits beside its GGUF. A deep tier started with one would still not be
asked: the vision probe (`PropsVisionProbe`, built by `build_vision` in the orchestrator's
`vision.py`) reads `/props` from the cortex's `inference.endpoint` alone, and the deep tier answers
at `CORTEX_BRAIN_ENDPOINT`.

**The cheap half landed 2026-08-03; the expensive half stays open, so this entry stays counted**
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) 2026-08-03 addendum). `HandoffRecord` grows
`opaque: bool` beside `tainted`, `EscalationSlot.snapshot` reads it off the live ledger,
`taint_ledger()` rebuilds it, the Redis codec writes and reads the key strictly (a missing one is a
corrupt record, like every other taint field), and the `HandoffStore` contract suite gains a
both-poles round trip that the fake and the Redis adapter both pass. The entry was right about
itself on every checkable claim, which is worth recording because this file's standing warning is
that a cost estimate is a hypothesis: the record really did carry the ledger minus the bit, both
consumers really are reached by the deep phase (`BrainPhase.run` opens the guardrail over the
rebuilt ledger and hands the same ledger to `record_exchange`), and "a record field, a codec line,
and the store contract's round trip" was the whole cost. It was right about the reachability too, so
the landing claims nothing more: `SwapConductor._prepare` still refuses an opaque turn before
anything is written, and the conductor test that drives the reachable ordering end to end now also
asserts the store saw **no write at all**, which is what makes the refusal, rather than the schema,
the thing keeping the far side clean today. What the bit buys is that neither consumer can be handed
a manufactured `False` the day the picture half relaxes that refusal, since a defaulted bit and a
real one look identical to both of them. The codec's treatment of a field it does not know was
checked rather than assumed, the same question that produced this entry's `Message.images` lesson:
`decode_record` reads keys by name, so an unknown key is ignored without error while a missing known
key raises into `HandoffStoreError`, which is why the bit is written **and** read rather than
defaulted, and why the strict-decode test now runs over all four taint fields. Proven by mutation
three ways in the codec (drop the encode line and thirteen store tests fail; default it on read with
`.get` and only the strict-decode test fails, which is the one that exists for that; drop both and
the contract round trip fails on `loaded == record`) and two ways in the core (drop it from
`snapshot` or from `taint_ledger()` and the two new brain-phase tests fail, each carrying a
tainted-but-not-opaque control arm so the measured difference is the bit and not the taint).
Observed live against the compose Redis rather than fakeredis alone: `"opaque": true` and `"opaque":
false` in the stored document, both read back exact on the record and on the ledger rebuilt from it.

## Trail

- 2026-07-19: written down here, having been missed when the slice closed, and named in ADR-0029's
  own Deferred paragraph. The area went 15 to 18 that day with this entry and two others, all three
  from the slice audit rather than from new work. It is what the fix to the opaque-turn escalation
  refusal opened, and it was recorded under vision rather than under untrusted content.
- 2026-08-03: the cheap half landed and the expensive half stayed open, so the count held at 17,
  this being the body-gateway precedent that a cell decremented for a half-closed entry is how an
  open deferral gets lost. The entry's name narrowed on the Open items line, the `opaque` bit
  leaving it while the picture stays, and the bullet keeps both with what the cheap half became. The
  landing carries a pointer from ADR-0029 decision 4, which owns the bit. Unusually for this
  backlog, the entry was right about itself on every checkable claim, including its cost.
- 2026-08-03: the index recorded why the distinction between a live refusal and a correct schema is
  drawn so hard on this landing, and the reason is this entry's own history. The last refusal in
  this area shipped inside a gated tool where it could never fire, with a test that reached the
  branch by calling `invoke` directly, which is why the conductor test now asserts the store saw no
  write at all: the refusal, not the schema, is what keeps the far side clean today.
- 2026-08-03: the index also recorded that the half landing that day needed no seam or port change
  at all and had been filed under its seam-change pickup heading anyway, the second entry that day
  to sit under that heading without belonging to it.
- 2026-08-03: the index named the bit's two consumers where this entry's own text leaves them
  unnamed, strict URL redaction and the durable-memory block, and recorded that both are real and
  that both are reached by the deep phase.
- 2026-09-13: re-derived and left open, with the capability claim corrected. The entry said no
  brain-tier candidate on the mount has a projector, and that is no longer true: the 31B QAT pick
  ships `gemma-4-31B-it-mmproj.gguf` beside its GGUF, and the Qwen 27B and 35B-A3B candidates each
  ship an `mmproj` file too. What actually keeps a replayed picture unreadable is that the model
  host has no setting to hand the deep tier one, so the sentence now names the wiring instead of
  the mount and the trigger reads on that. The rest holds unchanged: nothing in the brain declares
  an `AttachmentStore`, no store persists pixels, and `SwapConductor._prepare` still refuses an
  opaque turn on `slot.refs.taint.opaque` before the store is touched, which is what keeps the far
  side clean rather than the schema.
- 2026-09-19: re-derived against the handoff code rather than this file's description, with two
  stale claims fixed, one omitted defence named, a third prerequisite added and the trigger
  restated. The refusal holds as written: `SwapConductor._prepare` returns `OPAQUE_TURN_NOTE` on
  `slot.refs.taint.opaque` before the unhosted-tier check and before the store is read, and the one
  change to the deep phase since the last pass (a handoff cut mid tool call now ends rather than
  fails) does not reach it. `HandoffRecord` still carries `opaque`, the Redis codec still writes
  and reads it strictly, and `taint_ledger()` still rebuilds it. The codec still writes a message
  field by field with no `images` key, but this file left out that `EscalationSlot.snapshot` raises
  on an image in the tail, which it has done since 2026-07-18, the day before this entry was
  written, so a relaxed refusal would fail loudly rather than drop a picture. The description's
  sentence saying `HandoffRecord` lacks the bit, false since the cheap half landed, is now in the
  past tense. The brain tier's `extra` gained its prompt-cache size, and still carries no
  projector. The added prerequisite is the probe: `build_vision` points it at the cortex's
  inference endpoint, and nothing asks the deep endpoint whether it reads pictures. The old trigger
  was this entry's own prerequisites, one of which, the content-addressed store, waits for a
  consumer, and this entry is that consumer, so each waited on the other. The trigger now names the
  demand.
