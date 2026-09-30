# The cortex names answer for an extraction

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

Under the shipped names and descriptions, the cortex pick delegates an extraction with the `answer`
role and never `excerpt`, while the summaries and the lookups name their own role
([spawn spec uptake](../../readings/spawn-spec-uptake.md), "The role property"). An extraction
delegated as `answer` reads the sentence asking for one fact or saying that the text does not state
it; what that sentence does to a list-shaped extraction is unread.

Each row below was written down before it was drawn:

1. **The card**, the cortex tier's argv at `-ngl 99`, the first row's three asks at four draws a
   note, 48 turns. The rule: it replicates if the extraction asks again name `answer` more often
   than `excerpt`. Drawn: every extraction named `answer`, 16 of 16, so it replicates.
2. **A second extraction wording**, "Extract every number from the note below", on CPU in the first
   row's condition: `answer` 8 of 8, beside the "List" ask's 8 of 8, so the reading does not rest
   on one ask's verb.
3. **A new `excerpt` description**, "a list of every item of one kind the text states, each written
   exactly as the text writes it, for a subtask that asks for all of them rather than one fact",
   on CPU from a copy of the tree, all four asks, 16 turns: the extractions named `excerpt` 7 of 8
   and the summaries and lookups kept their own role 4 of 4 each, so it moves the cortex on this
   condition.
4. **That description on the card**, next: the condition of item 1, all four asks at
   `CORTEX_ROLE_UPTAKE_DRAWS=4`, 64 turns, `-k role`, with `CORTEX_ROLE_UPTAKE_EXCERPT` set to the
   new description. It replicates if the two extraction asks together name `excerpt` more often than
   `answer`, and the summary and the lookup each name their own role on at least 14 of 16. If it
   replicates, the description ships in `SHIPPED_ROLES` and ADR-0072 decision 6 states it. If it
   does not, the change is item 5.
5. **A name set, the maintainer's pick**, each redrawn through the same probe: the three sets
   ADR-0072 decision 7 lists (`precis`, `excerpt`, `answer`, shipped; `summarize`, `extract`,
   `lookup`, where `extract` is the verb of the measured extraction shape; `abridge`, `transcribe`,
   `cite`), or the shipped set with `excerpt` alone renamed, for example to `list`, a noun for the
   reply that matches the verb of the "List" ask. A name is a design pick and not the agent's.

Record the engine build, the argv and an `nvidia-smi` SM clock beside the card rows. Done when a
description or a name set that reads `excerpt` more often than `answer` on the card ships and
ADR-0072 states it, or the maintainer keeps the shipped names and descriptions.

## History

- 2026-09-29: Filed by the close of
  [R-749](749-the-cortex-uptake-of-the-role-property-is-unmeasured.md), whose CPU row read every
  extraction naming `answer`.
- 2026-09-30: Item 2 drawn on CPU, 16 turns: the "Extract every number" ask and the "List every
  date" ask each named `answer` 8 of 8, recorded in the readings record and ADR-0072. Open on
  item 1.
- 2026-09-30: Item 1 drawn on the card, 48 turns: every extraction named `answer`, 16 of 16, the
  summaries `precis` 15 of 16 and the lookups `answer` 16 of 16, so the CPU reading replicates.
  Item 3 drafted and drawn on CPU while the card was busy: `excerpt` 7 of 8. Recorded in the
  readings record and ADR-0072. Open on item 4, the card row of that description.
