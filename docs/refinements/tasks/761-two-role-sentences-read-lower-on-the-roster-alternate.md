# Two role sentences read lower on the roster alternate

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

On Qwen3.5-2B, the roster alternate, drawn on the card at seeds 1 to 8, the shipped `precis`
sentence took the figures-keeping summarization from 31 to 17 of 32, with 14 copies of the body,
and the `excerpt` sentence took the extraction from 27 to 10 of 32, each interval apart from its
plain cell's ([reply envelope](../../readings/reply-envelope.md), "The role sentences"). The
`answer` sentence read inside. The plain cells repeat the 2026-09-13 cells reply for reply, since
at one build a seeded draw returns the same reply, so a new seed base samples both columns again.

Written down before a row is drawn:

1. **A second seed base on the card**: the `llama-subagent-qwen` argv of the roster compose file at
   `-ngl 99`, cells figures `none` and `precis`, extract `none` and `excerpt`, each constrained at
   four bodies and eight draws a cell with `CORTEX_ENVELOPE_SEED=9`, in one server session, each
   sentence read from `SHIPPED_ROLES`, judged by `delivered` in `scripts/envelopejudges.py` under
   the tabled reading. A sentence's drop replicates where its interval is again apart from and
   lower than the plain cell's. An overlap leaves the first row as one seed base's result and the
   sentence shipped. Queued as row `761` of the unattended run at
   `measurements/sitting-2026-09-30c/`, last, and drawn only if the pace says it ends by 07:30.
2. **If a drop replicates**, how a role reads on a model its sentence lowers: a sentence chosen by
   the model after `SubagentRoster.resolve`, which keeps the roster from reading the role, or no
   sentence for that role, which for `precis` is item 2 of
   [R-760](760-the-reworded-precis-sentence-reads-below-the-plain-summary.md). Written as an
   ADR-0072 edit beside its reading.

Record the engine build, the argv and an `nvidia-smi` SM clock beside the row. Done when the row is
in the readings record and ADR-0072 states the result.

## History

- 2026-09-30: Filed when the alternate's first card row read the `precis` and `excerpt` sentences
  apart and lower on one seed base, and queued its second seed base behind R-760's and R-706's rows.
