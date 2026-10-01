# The reworded precis sentence reads below the plain summary

**Status:** done 2026-10-01
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

On the default pick on the card, the shipped `precis` sentence delivered the figures-keeping
summarization below the plain cell on both seed bases drawn: 20 of 32 (0.45 to 0.77) against 27 of
32 (0.68 to 0.93) at seeds 1 to 8, and 16 of 32 (0.34 to 0.66) against 23 of 32 (0.55 to 0.84) at
seeds 9 to 16, with 4 and then 7 copies of the body handed back `ok=True` against none ([role
sentences](../../readings/role-sentences.md)). Each pair of intervals overlaps, so by the rule
written before each row the rewording ships. Pooled, it reads 36 of 64 against 50 of 64, a count no
rule named before either row. At one build a seeded draw returns the same reply, so only a new seed
base samples again.

No `precis` sentence has read above its plain cell on any seed base or on either model drawn, and
among the runs it loses on this pick is the body handed back as a finished answer, which the plain
cell never returned here. That supports item 2, but no rule written before a row calls for it yet.

Written down before a row is drawn:

1. **A third seed base at twice the draws**: the compose argv at `-ngl 99`, the figures shape
   constrained, four bodies at sixteen draws a cell (`CORTEX_ENVELOPE_DRAWS=16`,
   `CORTEX_ENVELOPE_SEED=17`, so seeds 17 to 32), the plain cell and the shipped sentence in one
   server session, judged by `delivered` in `scripts/envelopejudges.py` under the tabled reading.
   Decided by Fisher's exact test, two-sided, on the two counts of 64: where p is below 0.05 and
   the sentence reads lower, it lowers delivery on this pick and the change is item 2; otherwise
   the sentence stays and the task closes as not shown to lower delivery. Priced at about 500 s on
   the card, from row `760`'s 291 s for two cells of 32 and a server load.
2. **No sentence for the role**: the cortex still names `precis`, and the subtask's own instruction
   sets the form. `SubagentRoles` accepts an entry with an empty instruction, as `excerpt` has, and
   `SubagentRole.applied` then leaves the instruction unchanged, so this is an empty `precis`
   instruction in `SHIPPED_ROLES` and a change to `test_roles.py`.

Record the engine build, the argv and an `nvidia-smi` SM clock beside the row. Done when the row is
in the readings record and ADR-0072 states the result.

## History

- 2026-09-30: Filed when the rewording shipped on one seed base, 20 of 32 against 27 of 32 plain.
- 2026-09-30: The second seed base, row `760` of the unattended run at
  `measurements/sitting-2026-09-30c/`, read 16 of 32 against 23, the intervals overlapping, so the
  rewording stays; the third seed base at sixteen draws a cell is item 1 now.
- 2026-10-01: item 1 queued second as row `760s17` in the unattended run logged at
  `measurements/sitting-2026-10-01/` (`760s17.log`, the replies under `760s17/`), on the compose
  argv at `-ngl 99` with `CORTEX_ENVELOPE_DRAWS=16` and `CORTEX_ENVELOPE_SEED=17`, the plain cell
  and then the shipped sentence in one server session; priced at 600 s. Predicted from the two
  seed bases pooled: plain 50 (44 to 56) against the sentence 36 (29 to 43) of 64, apart below.
- 2026-10-01: Done. Row `760s17` read 32 of 64 against 44 plain (`760s17.log` and `760s17/` under
  `measurements/sitting-2026-10-01/`), and Fisher's exact test gave p = 0.047, two-sided, with the
  sentence lower, so by the rule item 2 shipped: `precis` has an empty instruction in
  `SHIPPED_ROLES`, and `test_roles.py` asserts that only `answer` changes the instruction. Pooled
  over the three seed bases it reads 68 of 128 against 94, which no rule named. Both counts fell
  inside the predicted ranges, the plain cell at its low edge.
