# One sentence is appended for every roster entry and the entries do not agree about it

**Status:** open, actionable
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
