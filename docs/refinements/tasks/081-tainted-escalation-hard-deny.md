# A tainted turn cannot escalate to the brain model

**Status:** done 2026-07-17
**Area:** untrusted-content
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Escalating to the brain model evicts the other models and makes the machine busy for minutes,
so injected content must never be able to trigger it. The escalation trigger is a
`gated=True` built-in in `cortex_core/escalate.py`
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 1), which means both existing
protections apply without new mechanism. On an untainted turn the ADR-0022 card asks the user
first, with a per-tool reason saying what is actually true (the generic outbound and
irreversible wording would be false here). On a tainted turn the dispatcher refuses the call
outright and the confirmer is never consulted.

The model-authored `brief` is bounded by `MAX_BRIEF_CHARS` and refused whole rather than
truncated, and it travels with the record's serialized taint ledger rather than instead of it.

The opaque-turn refusal was deferred at first, because ADR-0030 assumed the vision slice
(ADR-0029) came first and it had not: `Message` held no pixels and no `opaque` flag existed, so
a refusal keyed on them would have had nothing to check.

**Closed 2026-07-18 with the vision slice's pixel-taint work
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)).** `TaintLedger` gained the `opaque`
flag, which `observe` sets when an UNTRUSTED result includes images. The refusal keys on that
flag rather than on image-bearing messages, which matters: the handoff record's message codec
lists fields by name, so a `Message.images` would be dropped on encode, and a refusal that
searched the loop tail for images would be looking for the one thing that cannot survive the
trip. `EscalationSlot.snapshot` also raises on an image-bearing loop tail, the same rule both
session stores apply, so a caller that skipped the tool still cannot persist a caption whose
picture is gone.

## History

- 2026-07-17: The trigger sub-slice was added, and the opaque-turn refusal was opened behind it.
- 2026-07-17: The same change gave the confirm card its first per-tool reason,
  `CORTEX_TOOLS_GATE_REASONS`, since the generic outbound and irreversible wording is false
  about a model swap.
- 2026-07-18: The opaque-turn refusal was closed with the vision slice's pixel-taint work.
- 2026-07-19: An audit corrected that closure. The refusal had shipped inside the escalation
  tool where it could never run, because `observe` cannot mark a turn opaque without also
  marking it tainted, and the dispatcher refuses every escalation after a capture before
  `invoke` runs. Its test reached the branch by calling `invoke` directly, and its control run
  used `tainted=False`, so nothing measured the flag. A reachable ordering was unhandled too:
  an approved escalation followed by an unconfirmed capture reached the record snapshot, whose
  image rule raised out of the conductor and killed the whole `Converse` stream. The refusal
  moved to `SwapConductor._prepare`, keyed on the same flag and tested end to end.
- 2026-07-19: The dead check in the escalation tool was removed, the conductor's refusal now
  returns a fixed note beside the already-active and store-failed ones, and the taint check is
  named as what closes the other ordering. The tests run through the real loop, the real tools
  and the real conductor.
- 2026-08-03: When the vision area added the `opaque` flag to the handoff record, it cited this
  history as its reason for separating schema work from live fixes, so that change's conductor
  test asserts the store saw no write at all.
