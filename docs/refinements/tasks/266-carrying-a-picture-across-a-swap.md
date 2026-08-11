# Carrying a picture across a model swap

**Status:** open, a seam or port change comes first
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** The `AttachmentStore` above, plus a brain-tier candidate that has a projector.

Carrying a picture, or at least the `opaque` bit, across a model swap. Named in ADR-0029's
own Deferred paragraph and written down here on 2026-07-19, having been missed when the slice
closed. Nothing persists an in-turn image: no session store, and no handoff record either, whose
codec enumerates message fields by name so a `Message.images` would have been dropped in
silence. The **user-visible** consequence is live: a turn that looked at the screen cannot hand
over to the deep model at all, and the conductor ends it with a note telling the user to ask
again in a fresh message. `HandoffRecord` does not carry the `opaque` bit either, so
`taint_ledger()` rebuilds it at `False`; that is sound only because no opaque turn can reach a
record (the conductor refuses first), and carrying the bit as defence in depth is the cheap half
of this entry. The expensive half is pixels themselves, which wants the `AttachmentStore` above,
and a capability argument still says no: no brain-tier candidate on the mount has a projector,
so a replayed picture would be unreadable even if it survived.

**The cheap half landed 2026-08-03; the expensive half stays open, so this entry stays counted**
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) 2026-08-03 addendum). `HandoffRecord` grows
`opaque: bool` beside `tainted`, `EscalationSlot.snapshot` reads it off the live ledger,
`taint_ledger()` rebuilds it, the Redis codec writes and reads the key strictly (a missing one is
a corrupt record, like every other taint field), and the `HandoffStore` contract suite gains a
both-poles round trip that the fake and the Redis adapter both pass. The entry was right about
itself on every checkable claim, which is worth recording because this file's standing warning is
that a cost estimate is a hypothesis: the record really did carry the ledger minus the bit, both
consumers really are reached by the deep phase (`BrainPhase.run` opens the guardrail over the
rebuilt ledger and hands the same ledger to `record_exchange`), and "a record field, a codec line,
and the store contract's round trip" was the whole cost. It was right about the reachability too,
so the landing claims nothing more: `SwapConductor._prepare` still refuses an opaque turn before
anything is written, and the conductor test that drives the reachable ordering end to end now also
asserts the store saw **no write at all**, which is what makes the refusal, rather than the
schema, the thing keeping the far side clean today. What the bit buys is that neither consumer can
be handed a manufactured `False` the day the picture half relaxes that refusal, since a decayed
bit and an honest one look identical to both of them. The codec's treatment of a field it does not
know was checked rather than assumed, the same question that produced this entry's
`Message.images` lesson: `decode_record` reads keys by name, so an unknown key is ignored in
silence while a missing known key raises into `HandoffStoreError`, which is why the bit is written
**and** read rather than defaulted, and why the strict-decode test now runs over all four taint
fields. Proven by mutation three ways in the codec (drop the encode line and thirteen store tests
redden; default it on read with `.get` and only the strict-decode test reddens, which is the one
that exists for that; drop both and the contract round trip reddens on `loaded == record`) and two
ways in the core (drop it from `snapshot` or from `taint_ledger()` and the two new brain-phase
tests redden, each carrying a tainted-but-not-opaque control arm so the measured difference is the
bit and not the taint). Observed live against the compose Redis rather than fakeredis alone:
`"opaque": true` and `"opaque": false` in the stored document, both read back exact on the record
and on the ledger rebuilt from it.

## Trail

- 2026-07-19: written down here, having been missed when the slice closed, and named in
  ADR-0029's own Deferred paragraph. The area went 15 to 18 that day with this entry and two others,
  all three from the slice audit rather than from new work. It is what the fix to the opaque-turn
  escalation refusal opened, and it was recorded under vision rather than under untrusted content.
- 2026-08-03: the cheap half landed and the expensive half stayed open, so the count held at 17,
  this being the body-gateway precedent that a cell decremented for a half-closed entry is how an
  open deferral gets lost. The entry's name narrowed on the Open items line, the `opaque` bit
  leaving it while the picture stays, and the bullet keeps both with what the cheap half became. The
  landing carries a pointer from ADR-0029 decision 4, which owns the bit. Unusually for this
  backlog, the entry was right about itself on every checkable claim, including its cost.
- 2026-08-03: the index recorded why the distinction between a live refusal and an honest schema is
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
