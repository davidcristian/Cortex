# One sentence is appended for every roster entry and the entries do not agree about it

**Status:** declined 2026-08-30
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

`REPLY_INSTRUCTION` is a module constant and `instruct_reply` appends it to the subtask of every
tool-less subagent, whichever roster entry runs it. Measured at 288 runs a pick, the entries do not
answer the same way. It recovers the default pick's narrating shape from 9 of 32 to 29 of 32 and
costs its other two shapes a draw each. It leaves the roster alternate a little better overall, 76
of 96 to 83 of 96, on a shape that is not the one it was written for. It leaves gemma-4-E2B worse
overall, 84 of 96 against 90 of 96. And it takes Qwen3.5-0.8B from 70 of 96 to 66, so the failing
side is two picks of five, on opposite sides of the template column, which means a per-entry
wording cannot be derived from that column alone.

Nothing shipped stands on the failing entries: the compose default is gemma-4-E4B and the roster
alternate is Qwen3.5-2B, and both gain. But the E2B is a named entry of the subagent row in
[ADR-0004](../../adr/ADR-0004-model-lineup.md), one `CORTEX_MODEL_FILE_SUBAGENT` away, and until
this was measured nothing said the override costs answers rather than only speed. A second env
variable is not the answer: ADR-0028 decision 7 stands, since a setting that could leave the
grammar on with the sentence off is a setting for reproducing a defect. What the reading argued for
is a per-entry wording, most likely a `SubagentProfile` field, which is a port change.

## History

- 2026-08-28: opened by the close of
  [R-481](481-the-sentence-is-measured-on-one-pick.md), which asked two more picks whether the
  shipped sentence helps them and found one it hurts.
- 2026-08-28: amended by the close of
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which measured the row's last two
  entries and put the failing side at two picks rather than one, with different mechanisms: the
  0.8B writes nothing to the reasoning channel and instead hands the instruction back, once as a
  paraphrase of `REPLY_INSTRUCTION` offered as the answer.
- 2026-08-30: declined by ADR-0028 decision 8. Every claim it makes about the tree held, and the
  thing that decides it is one the entry never states: a `SubagentProfile` is keyed by roster name,
  and the two picks the sentence costs are lineup entries reached by pointing
  `CORTEX_MODEL_FILE_SUBAGENT` at another GGUF in a compose `command:` the brain never reads.
  `SingleResidentModelManager` matches that name against itself and dials an endpoint, so a wording
  filed under `subagent` would describe whatever weights the container happened to load. The field
  would also ship empty everywhere, both picks a stack ships being on the gaining side, and the only
  value an operator could set with confidence is the empty one, which is decision 7's setting
  rebuilt per entry. Nothing measured supports a second wording either: no milder sentence has been
  asked of the E2B, and on the 0.8B the failure is the request handed back, which a softer sentence
  gives more to copy. The entry's third suggestion did happen: the ADR now scopes the sentence to
  the picks this repo ships rather than to the tier, and the runbook's override table gains the four
  conditions its rates are a reading under. What the decline hands forward is
  [R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md), the identity a per-entry value
  would need to be filed under. Worth designing with
  [R-485](485-a-roster-description-never-says-whether-the-entry-answers.md), which needs the same
  per-entry boundary for a different value.
