# The cortex names answer for an extraction

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

On the cortex pick, drawn on CPU, all 8 extraction asks ("List every date the note below
mentions") were delegated with the `answer` role and none with `excerpt`, while the summaries and
the lookups named their own role 8 of 8 each
([spawn spec uptake](../../readings/spawn-spec-uptake.md), "The role property"). By the rule
written before that row, the names or descriptions mislead the cortex on extraction, and an
extraction delegated as `answer` reads the sentence asking for one fact or saying that the text
does not state it. It is one condition's row, so it needs a replication before any name or
description changes.

Written down before the replication is drawn:

1. **The same asks on the card**, the cortex tier's compose argv at `-ngl 99`, with
   `CORTEX_ROLE_UPTAKE_DRAWS=4` over the first three asks (48 turns, `-k "role and not numbers"`),
   through the command in [subagents validation](../../runbooks/subagents-validation.md). It
   replicates if the extraction asks again name `answer` more often than `excerpt`.
2. **A second extraction wording**, "Extract every number from the note below", the verb of the
   measured extraction shape, so the reading does not rest on one ask's "List". Drawn on CPU in the
   first row's condition as the probe's `numbers` ask: it named `answer` 8 of 8 and `excerpt` never,
   and the "List" ask drawn beside it did the same, so the CPU reading holds on both wordings.
3. **If it replicates**, the change is the maintainer's pick among the name sets ADR-0072 decision
   7 lists, or a new `excerpt` description, each redrawn through the same probe. What the `answer`
   sentence does to a list-shaped extraction is also unread.

Record the engine build, the argv and an `nvidia-smi` SM clock beside the card rows. Done when the
replication is in the readings record and ADR-0072 states it.

## History

- 2026-09-29: Filed by the close of
  [R-749](749-the-cortex-uptake-of-the-role-property-is-unmeasured.md), whose CPU row read every
  extraction naming `answer`.
- 2026-09-30: Item 2 drawn on CPU, 16 turns: the "Extract every number" ask and the "List every
  date" ask each named `answer` 8 of 8, recorded in the readings record and ADR-0072. Open on
  item 1.
