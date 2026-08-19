# The seam carries one detail string, so two facts are one sentence

**Status:** open, a seam or port change comes first
**Area:** seam-transport
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-19 by the close of [304](304-spill-rides-the-residency-report.md), which put a
second annotator on a **serving** residency report. `HealthReply.detail` is one string
([body.proto](../../../proto/body.proto)), so when a peer tier is down and the last handoff
spilled, the two are joined with a semicolon by
[residency_state.with_note](../../../brain/packages/core/src/cortex_core/residency_state.py) and
the overlay renders the pair as one line after "Brain ready". That is the honest reading of a
one-string field and it is already at its limit: a third annotator would make a tooltip nobody
reads to the end, and a client cannot style, order, or dismiss one fact without the other because
it never learns there were two.

What would close it is a shaped detail rather than a longer one: a repeated field on the reply, or
a message carrying a short code plus its sentence, so the overlay can render one line per fact and
decide for itself which deserves the tooltip's first line. It is a proto change and therefore a
change to the one file both toolchains generate from, which is why this waits rather than being
bundled: the join costs nothing today, and the shape wanted here should be designed against the
second client that needs it rather than against the first that noticed.

## Trail

- 2026-08-19: Opened by the close of [304](304-spill-rides-the-residency-report.md), which chose
  to say both facts rather than let whichever wrote last win, and recorded the display compromise
  that choice leaves: one field, one sentence, two remedies.
