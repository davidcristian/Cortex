# The excerpt sentence lowers the extraction on the roster alternate

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

On Qwen3.5-2B, the roster alternate, the shipped `excerpt` sentence took the extraction from 27 to
10 of 32 at seeds 1 to 8 and from 22 to 8 of 32 at seeds 9 to 16 on the card, each interval apart
from and lower than the plain cell's, so by the rule written before the second row the drop
replicates ([role sentences](../../readings/role-sentences.md)). The runs it loses mostly write the
instructions back or stop at the cap repeating numbers. On the default pick, drawn on CPU, it read
26 of 32 against 30, inside the plain interval, so no reading shows it helping either model.

The change is no sentence for the role. The cortex still names `excerpt`, which its description
decides (29 of 32 extractions named it on the card), and the subtask's own instruction sets the
form. A sentence chosen per model after `SubagentRoster.resolve` is the other way, and it keys a
role to roster entry names, which are deployment config, the reason ADR-0072 decision 5 gives for a
role holding no model preference.

1. `SubagentRoles` accepts an entry whose instruction is empty and still rejects an empty name or
   description; `SubagentRole.applied` already leaves the instruction unchanged when the sentence
   is empty. The construction test in `brain/packages/core/tests/test_roles.py` and
   `test_every_shipped_role_resolves_and_changes_the_instruction` change with it.
2. `SHIPPED_ROLES` gives `excerpt` an empty instruction.
3. ADR-0072 decisions 1 and 6 and its Consequences, and `docs/modules/brain-core-subagents.md`,
   say a role may have no sentence and that `excerpt` has none.

The check change in item 1 is also item 2 of
[R-760](760-the-reworded-precis-sentence-reads-below-the-plain-summary.md), for `precis`, if that
task's row separates the two cells. Done when `excerpt` ships without a sentence and ADR-0072 states
it.

## History

- 2026-09-30: Filed when the second seed base on the alternate, row `761` of the unattended run at
  `measurements/sitting-2026-09-30c/`, read the `excerpt` sentence apart and lower again and the
  `precis` rewording inside the plain interval.
