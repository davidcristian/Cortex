# Tainted-escalation hard-deny

**Status:** landed 2026-07-17
**Area:** untrusted-content
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The hard-deny rides the gated `escalate_to_brain` built-in
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 1, the trigger sub-slice).
The escalation trigger is a `gated=True` built-in (`cortex_core/escalate.py`), so both existing
protections cover the most disruptive action in the system at zero new mechanism: on an
untainted turn the ADR-0022 card asks first (with a per-tool reason saying what is true, that
the deep model takes over and the machine is busy for minutes, since the generic
outbound/irreversible line would be false), and on a tainted turn the dispatcher's existing
hard-deny blocks the call with the confirmer never consulted, so injected content can never
force the eviction (pinned by an approving-confirmer test, mutation-proven by weakening the
gate check). The model-authored `brief` is bounded (`MAX_BRIEF_CHARS`, refused whole, never
truncated) before it can enter the handoff record, and it rides WITH the record's serialized
taint ledger, never instead of it. **One piece of the ADR's trigger sub-slice is consciously
deferred: the opaque-turn refusal.** ADR-0030 assumed the vision slice (ADR-0029) lands first
("this slice lands after the vision slice"), but the repo sequenced the handoff sub-slices
ahead of it: ADR-0029 is designed and unimplemented, `Message` carries no pixels and no
`opaque` bit exists, so a refusal keyed on them has nothing to check and faking one would be a
gate that cannot fail. It lands with (or immediately after) the vision slice's pixel-taint
increment, as a typed refusal in `escalate.py` telling the model to ask the user to retry in a
fresh message, keeping escalation from quietly widening pixel persistence (the ADR-0029 store
invariant the handoff record already honors).

**Closed 2026-07-18 with the vision slice's pixel-taint increment
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)).** `TaintLedger` gained the `opaque`
bit, set by `observe` when an UNTRUSTED result carries images, and `EscalateToBrainTool`
refuses an opaque turn ahead of every other validation with a typed message telling the model
to answer what it can and ask the user to retry in a fresh message. Two corrections to what
the entry expected. **The refusal keys on the bit, not on image-bearing messages**, and that
is load-bearing rather than cosmetic: the handoff record's message codec enumerates fields by
name, so a `Message.images` would have been silently dropped on encode, and a refusal that
hunted for images in the loop tail would therefore have been checking the one thing that
cannot survive the trip. The bit stays true exactly where the pixels cannot travel. **The
structural backstop landed with it**: `EscalationSlot.snapshot` now raises on an image-bearing
loop tail, the same rule both session stores enforce, so even a caller that bypassed the tool
cannot persist a caption whose picture is gone. The refusal is pinned against its literal text
with a transparent-tainted control arm, so it measures the opaque bit and not taint.

## Trail

- 2026-07-17: The trigger sub-slice landed and took the area's count from 13 to 14, opening the
  opaque-turn escalation refusal behind it.
- 2026-07-17: The same landing gave the confirm card its first per-tool reason,
  `CORTEX_TOOLS_GATE_REASONS`, since the generic outbound and irreversible line is false about a
  model swap.
- 2026-07-18: That refusal closed with the vision slice's pixel-taint increment, taking the count
  back to 13.
- 2026-07-19: The audit of that slice corrected the closure, and the index reads against the
  entry's own account above. It found the refusal shipped in the escalation tool where it could
  never fire, since `observe` cannot mark a turn opaque without marking it tainted and the gated
  tool's hard-deny answers every escalation after a capture before `invoke` runs, while its test
  reached the branch by calling `invoke` directly and its control arm ran with `tainted=False`,
  so nothing measured the bit. The reachable ordering was unhandled too, an approved escalation
  followed by an ungated capture reaching the record snapshot whose image invariant raised out
  of the conductor and killed the whole Converse stream, so the refusal moved to
  `SwapConductor._prepare` keyed on the same bit and pinned end to end; the entry stayed closed,
  the count stayed 13, and what the fix opened is recorded under vision.
- 2026-07-19: The index recorded the rest of that audit's finding: the deferral had been closed
  with exactly the gate that cannot fail it was written down to avoid, the refusal in the
  conductor answers a fixed note beside the already-active and store-failed ones, the dead check
  in the escalation tool is gone, and the taint gate is named as what closes the other ordering.
  The pinning runs through the real loop, the real tools and the real conductor.
- 2026-08-03: The vision area's landing of the `opaque` bit on the handoff record cited this
  refusal's history as its reason for drawing the schema-versus-live-fix distinction so hard, a
  refusal here having shipped inside a gated tool where it could never fire with a test that
  reached the branch by calling `invoke` directly, so that landing's conductor test asserts the
  store saw no write at all.
