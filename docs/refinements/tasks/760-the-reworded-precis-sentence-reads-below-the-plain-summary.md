# The reworded precis sentence reads below the plain summary

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

On the default pick on the card, the shipped `precis` sentence delivered the figures-keeping
summarization 20 of 32 (0.45 to 0.77) against 27 of 32 (0.68 to 0.93) without a sentence, with 4
copies of the body against none ([reply envelope](../../readings/reply-envelope.md), "The role
sentences"). The intervals overlap, so by the rule written before the row the rewording shipped.
Both cells were drawn at seeds 1 to 8, and at one build a seeded draw returns the same reply, so
drawing the same cells again at those seeds repeats them rather than sampling again.

Written down before a row is drawn:

1. **A second seed base on the card**: the compose argv at `-ngl 99`, the figures shape
   constrained, four bodies at eight draws a cell with `CORTEX_ENVELOPE_SEED=9`, the plain cell and
   the shipped sentence in one server session, judged by `delivered` in `scripts/envelopejudges.py`
   under the tabled reading. The rewording stays if its interval overlaps the plain cell's. If it is
   apart and lower, the sentence lowers delivery on this pick, and the change is item 2.
2. **No sentence for the role**: the cortex still names `precis`, and the subtask's own instruction
   sets the form. `SubagentRoles` rejects an entry with an empty instruction today, so this is a
   change to that check and its tests; `SubagentRole.applied` already leaves the instruction
   unchanged when the sentence is empty.

Record the engine build, the argv and an `nvidia-smi` SM clock beside the row. Done when the row is
in the readings record and ADR-0072 states the result.

## History

- 2026-09-30: Filed when the rewording shipped on one seed base, 20 of 32 against 27 of 32 plain.
