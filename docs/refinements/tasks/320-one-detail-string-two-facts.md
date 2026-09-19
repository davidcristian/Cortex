# The seam carries one detail string, so two facts are one sentence

**Status:** open, a seam or port change comes first
**Area:** seam-transport
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-19

Opened 2026-08-19 by the close of [304](304-spill-rides-the-residency-report.md), which put a second
annotator on a **serving** residency report. `HealthReply.detail` is one string
([body.proto](../../../proto/body.proto)), so when a peer tier is down and the last handoff spilled,
the two are joined with a semicolon by
[residency_state.with_note](../../../brain/packages/core/src/cortex_core/residency_state.py) and the
overlay renders the pair as one line after "Brain ready". That is the correct reading of a
one-string field and it is already at its limit: a third annotator would make a tooltip nobody reads
to the end, and a client cannot style, order, or dismiss one fact without the other because it never
learns there were two.

What would close it is a shaped detail rather than a longer one: a repeated field on the reply, or a
message carrying a short code plus its sentence, so the overlay can render one line per fact and
decide for itself which deserves the tooltip's first line. It is a proto change and therefore a
change to the one file both toolchains generate from, which is why this waits rather than being
bundled: the join costs nothing today, and the shape wanted here should be designed against the
second client that needs it rather than against the first that ran into it.

## Trail

- 2026-08-19: Opened by the close of [304](304-spill-rides-the-residency-report.md), which chose
  to say both facts rather than let whichever wrote last win, and recorded the display compromise
  that choice leaves: one field, one sentence, two remedies.
- 2026-09-13: Re-derived, unchanged, and still at two annotators rather than three.
  `HealthReply { bool ready = 1; string detail = 2; }` is the proto's shape today, and
  `with_note` has exactly two callers, `residency_tiers.py` for a peer that is down and
  `residency_pace.py` for a handoff that spilled, joined by the semicolon this entry describes.
  `Health` in `server.py` passes whatever the residency composed, so the overlay still learns one
  string and cannot tell that two facts arrived. The client that would decide the shape is still
  the only client, so the entry waits where it was left.
- 2026-09-19: Re-derived, and still at two annotators. `HealthReply` is unchanged in the proto,
  `with_note` still has the same two callers (a third mention, in `residency_probe.py`, is a
  docstring naming the join), and `linkState.ts` still renders the joined string after "Brain
  ready" through one `withDetail` call. The one candidate for a third note since the last reading,
  a failed handoff's reason, was declined on 2026-09-15 by
  [R-379](379-a-settled-reason-nothing-reads-back.md), partly because `with_note` annotates only a
  serving report, so nothing has moved this entry toward the tooltip it warns about.
