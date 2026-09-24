# The health reply has one detail string, so two facts become one sentence

**Status:** done 2026-09-24
**Area:** rpc-transport
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)

`HealthReply.detail` is one string ([body.proto](../../../proto/body.proto)), so when a peer tier is
down and the last handoff spilled, the two notes are joined with a semicolon by
[residency_state.with_note](../../../brain/packages/core/src/cortex_core/residency_state.py) and the
overlay renders the pair as one line after "Brain ready". That is the correct use of a one-string
field and it is already at its limit: a third note would make a tooltip nobody reads to the end,
and a client cannot style, order or dismiss one fact without the other because it never learns
there were two.

The fix is a structured detail rather than a longer one: a repeated field on the reply, or a
message with a short code plus its sentence, so the overlay can render one line per fact. It is a
proto change, and therefore a change to the one file both toolchains generate from, which is why it
waits: the join costs nothing today, and the shape should be designed against the second client
that needs it rather than the first that ran into it.

## History

- 2026-08-19: Opened by the close of [304](304-a-spilled-handoff-is-only-ever-in-the-log.md), which chose to
  report both facts rather than let whichever wrote last win, and recorded the display compromise
  that leaves: one field, one sentence, two remedies.
- 2026-09-13: Checked again, unchanged, and still at two notes rather than three.
  `HealthReply { bool ready = 1; string detail = 2; }` is the proto today, and `with_note` has
  exactly two callers, `residency_tiers.py` for a peer that is down and `residency_pace.py` for a
  handoff that spilled, joined by the semicolon described above. `Health` in `server.py` passes
  whatever the residency composed, so the overlay still receives one string and cannot tell that
  two facts arrived. The client that would decide the shape is still the only client.
- 2026-09-19: Checked again, and still at two notes. `HealthReply` is unchanged in the proto,
  `with_note` still has the same two callers (a third mention, in `residency_probe.py`, is a
  docstring describing the join), and `linkState.ts` still renders the joined string after "Brain
  ready" through one `withDetail` call. The one candidate for a third note since the last reading,
  a failed handoff's reason, was declined on 2026-09-15 by
  [R-379](379-a-settled-reason-nothing-reads-back.md), partly because `with_note` annotates only a
  serving report.
- 2026-09-24: Built, since the reason to wait was a second client and nothing about the shape
  depended on one. `HealthReply` gained `repeated HealthNote notes = 3`, a `HealthNote` being one
  sentence. `ResidencyReport` keeps its notes as a tuple that `with_note` appends to, `Health`
  sends one `HealthNote` per note and still joins them into `detail` for a client built before the
  field, and the body passes them through `RpcHealth` and `LinkStatus` to the overlay, whose ready
  label is `Brain ready` with one line per note. A code beside each sentence, which is what would
  let a client style or dismiss one note, waits for a client that needs it and for its names:
  [719](719-a-health-note-has-no-code.md).
