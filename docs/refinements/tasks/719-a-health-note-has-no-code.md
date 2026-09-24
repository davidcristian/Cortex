# A health note has no code

**Status:** open, waiting for a consumer
**Area:** rpc-transport
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-09-24
**Trigger:** A client that must treat one serving note apart from the others: style a missing peer tier differently from a slow last handoff, order them by its own rule, or let the user dismiss one.

`HealthNote` in [body.proto](../../../proto/body.proto) has one field, the sentence. The overlay
shows each note on its own line and needs nothing more, so a code was left out rather than named
early. A code is a family of wire names (one per note: the missing peer tier, the slow last
handoff), so it needs its names picked before it is added, and it freezes once a client outside
this repository reads it. Adding it is `string code = 2` on `HealthNote`, set beside each
`with_note` call in `residency_tiers.py` and `residency_pace.py`, which needs `with_note` to take a
code with the sentence.

## History

- 2026-09-24: Opened by the close of [R-320](320-one-detail-string-two-facts.md), which gave the
  health reply one note per fact and left the code out until a client needs one.
