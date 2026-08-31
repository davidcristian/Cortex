# One sentence is appended for every roster entry and the entries do not agree about it

**Status:** declined 2026-08-30
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-08-28 by the close of
[R-481](481-the-sentence-is-measured-on-one-pick.md), which asked two more picks whether the shipped
sentence helps them and found one that it hurts.

`REPLY_INSTRUCTION` is a module constant and `instruct_reply` appends it to the subtask of every
tool-less subagent, whichever roster entry runs it. Measured at 288 runs a pick, the three entries of
the subagent tier that have been asked do not answer the same way. It recovers the default pick's
narrating shape from 9 of 32 to 29 of 32 and costs its other two shapes a draw each. It leaves the
roster alternate a little better overall, 76 of 96 to 83 of 96, on a shape that is not the one it was
written for. And it leaves **gemma-4-E2B worse overall**, 84 of 96 against 90 of 96, buying a
summarization it already mostly answered and losing a one-fact lookup from 31 of 32 to 24.

Nothing shipped stands on the failing entry: the compose default is gemma-4-E4B and the roster
alternate is Qwen3.5-2B, and both pay. But the E2B is a named entry of the subagent row in
[ADR-0004](../../adr/ADR-0004-model-lineup.md), one `CORTEX_MODEL_FILE_SUBAGENT` away, and until this
was measured nothing in the tree said the override costs answers rather than only speed.

**Why a knob is not the answer.** The instruction addendum's decision 4 is right and should stay: a
second env var that could leave the grammar on with the sentence off is a knob for reproducing a
defect, and an operator has no way to know which side of the split a pick is on. What the reading
argues for is narrower, that the wording is **per entry** rather than per deployment, since the entry
is the thing that decides.

**What would close it.** A decision at
[ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) about where a per-entry wording
lives, and then the ordinary slice. The shape the reading points at is a `SubagentProfile` field
carrying an optional override of `REPLY_INSTRUCTION`, defaulting to the shipped sentence so the
common case types nothing, set per roster entry beside the resources and the description that are
already per entry, and threaded to `task_messages` the way `constrain` already is. That is a port
change: `SubagentProfile` is a core dataclass the roster is parsed into from
`CORTEX_SUBAGENTS_ROSTER__*`, so the field has to survive the parse, the contract test and the fake
before any wording moves.

Three things worth deciding at the same time, because each changes what the field would hold.

- **Whether the right per-entry value is a different sentence or no sentence.** The E2B's losses are
  not the wording being wrong for it; they are the sentence pushing a template that answers "do not
  think" by dropping the block, and the answer then going to the reasoning channel on 14 draws of 96.
  A milder wording might push less. Nothing measured says a wording exists that recovers its
  summarization without costing its lookup, and one arm would find out.
- **Whether the entry should be asked rather than configured.** The predictor is one HTTP call
  against a loaded server, which is
  [R-475](475-a-tier-can-be-asked-what-its-template-answers.md), and an entry whose template closes
  an empty thought is exactly the entry that needs no sentence and pays nothing for one. If that call
  lands, the wording could follow the rendering instead of a config line, and this becomes a
  consumer of it rather than a field.
- **Whether the default should move at all.** The honest reading is that the sentence is a net gain
  on two of three measured entries and a net loss on one, so the shipped default stays; but the
  argument for it is now "it helps the picks we ship" and not "it helps this tier", and the ADR
  should say the narrower thing.

**Amended 2026-08-28 by the close of
[R-483](483-the-rest-of-the-subagent-tier-is-unasked.md)**, which measured the row's last two
entries. The count above is now three gains and two losses out of five: Qwen3.5-4B goes 91 of 96 to
94 and **Qwen3.5-0.8B goes 70 of 96 to 66**, so the failing side of this entry is two picks rather
than one, and they are on opposite sides of the template column, which means a per-entry wording
cannot be derived from that column alone. The 0.8B's loss also has a different mechanism from the
E2B's: it writes nothing to the reasoning channel at all, and what it does instead is hand the
instruction back, once as a paraphrase of `REPLY_INSTRUCTION` itself offered as the answer. A milder
wording is a plausible remedy on the E2B and is not obviously one here. Worth designing together
with [R-485](485-a-roster-description-never-says-whether-the-entry-answers.md), which needs the same
per-entry seam for a different value.

## Trail

- 2026-08-28: opened by the close of
  [R-481](481-the-sentence-is-measured-on-one-pick.md), which asked two more picks whether the
  shipped sentence helps them and found one it hurts.
- 2026-08-28: amended by the close of
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which measured the row's last two
  entries and put the failing side at two picks rather than one, on opposite sides of the template
  column and with different mechanisms.
- 2026-08-30: declined by the ADR-0028 per-entry wording addendum. Every claim it makes about the
  tree held, and the thing that decides it is one the entry never states: a `SubagentProfile` is
  keyed by roster **name**, and the two picks the sentence costs are lineup entries reached by
  pointing `CORTEX_MODEL_FILE_SUBAGENT` at another GGUF in a compose `command:` the brain never
  reads. `SingleResidentModelManager` matches that name against itself and dials an endpoint, so a
  wording filed under `subagent` would describe whatever weights the container happened to load. The
  field would also ship empty everywhere, both picks a stack ships being on the gaining side, and
  the only value an operator could set with confidence is the empty one, which is the instruction
  addendum's decision 4 knob rebuilt per entry. Nothing measured supports a second wording either:
  no milder sentence has been asked of the E2B, and on the 0.8B the failure is the ask handed back,
  once as a paraphrase of `REPLY_INSTRUCTION` itself, which a softer sentence gives more to copy.
  What the entry's third bullet asked for did land: the ADR now scopes the sentence to the picks
  this repo ships rather than to the tier, and the runbook's override table gains the four
  conditions its rates are a reading under. What the decline hands forward is
  [R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md), the identity a per-entry value
  would need to be filed under.
