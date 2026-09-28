# A role sentence is unmeasured against the envelope readings

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

The three shipped subagent roles each append one sentence to a subtask, naming the form its reply
takes (`SHIPPED_ROLES` in `brain/packages/core/src/cortex_core/roles.py`). No reading measures
those sentences. The case for them rests on related wordings in
[reply envelope](../../readings/reply-envelope.md): a summarization delivered 10 of 40 under the
envelope alone and 39 of 40 when the subtask named what the reply must contain, and a genre wording
read 30 of 32 beside 29 of 32 for the generic one.

Two questions, each drawn through the envelope harness
(`brain/packages/orchestrator/tests/test_envelope_cost_live.py`, judged by
`scripts/envelopejudges.py`) on the default pick and the Qwen3.5-2B roster alternate:

1. Does a role sentence change delivery? Each measured shape with and without the matching role's
   sentence appended (`precis` on the figures-keeping summarization, `excerpt` on the extraction,
   `answer` on the lookup), under the shipped `REPLY_INSTRUCTION`. A null result is both columns
   inside each other's Wilson interval on every cell, and it leaves the roles in place as a form
   the cortex can name, with the ADR saying the sentences are not shown to help.
2. Do the `excerpt` sentence and `REPLY_INSTRUCTION` conflict? The first asks for items as the text
   writes them and the second forbids repeating the input back. A conflict shows as copies counted
   on the extraction with the role that the extraction without it does not have.

The harness sends its instruction through `CORTEX_ENVELOPE_INSTRUCTION`, so a role row is the
instruction with the sentence appended, and the judge table matches it by its opening. Record the
engine build, the argv and an `nvidia-smi` SM clock beside any GPU row. Done when the rows are in
the readings record and ADR-0072 states the result.

## History

- 2026-09-28: Filed when [R-272](272-more-subagent-roles.md) shipped the roles without a reading of
  their own.
