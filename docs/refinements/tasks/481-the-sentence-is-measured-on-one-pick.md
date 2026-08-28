# The sentence every constrained subagent now carries is measured on one pick

**Status:** landed 2026-08-28
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-08-28 by the close of
[R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which shipped `REPLY_INSTRUCTION` to
every constrained subagent on 288 runs of one model.

`REPLY_INSTRUCTION` is appended to the subtask of **every** tool-less subagent, whichever roster
entry runs it ([ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)). Every reading behind it is
gemma-4-E4B QAT q4_0, the default entry, on one llama.cpp build at one placement. The roster's
shipped alternate is Qwen3.5-2B Q4_K_M, from a different family with a different chat template and a
different reasoning switch, and it has never been asked whether the sentence helps it, does nothing
to it, or costs it. The measurement is symmetric across the two, so the question is cheap to ask:
`docker/docker-compose.subagents-roster.yml` starts the alternate, and
`brain/packages/orchestrator/tests/test_envelope_cost_live.py` runs the same three arms over the
same bodies against whatever `CORTEX_SUBAGENTS_ENDPOINT` names.

Two reasons this is worth asking rather than assuming.

**The defect it repairs is not a property of the wording.** It is a property of a small model meeting
a grammar that admits prose and treating a plan as its whole output, and nothing measured says
another pick does the same thing at the same rate. A pick that never narrated would carry the
sentence for nothing, which is only a token or two, and a pick that narrates differently might want
different words.

**The cost it carries is a property of the tier's own machinery.** The 8 draws in 96 that wrote the
answer into the reasoning channel are on a gemma template, six of them opening with a malformed
channel marker. Whether the Qwen template does anything of the kind under the same push is unknown,
and it is the same question
[R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md) asks about the flags, on the other
axis.

**What would close it.** The three arms (`raw`, `bare`, `constrained`) over the four bodies at the
same draw count on the roster alternate, on the summarization shape at least, since that is the one
the effect lives on, judged the same way. Three outcomes are worth acting on: the sentence helps the
alternate too and the record simply gains a second pick; it does nothing there, in which case the
constant is the default pick's and the roster entry is where a per-entry wording would belong; or it
costs the alternate, which would make this a `SubagentProfile` field rather than a module constant
and is the only outcome that moves code.

## Trail

- 2026-08-28: opened by the close of
  [R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which shipped a sentence to every
  roster entry on 288 runs of one of them.
- 2026-08-28: Landed. Two more subagent-tier entries were asked the same question through the same
  committed harness, the same four bodies, the same three subtask shapes, the same eight draws and
  the same `-ngl 99` substitution: the **Qwen3.5-2B roster alternate** and **gemma-4-E2B**, 288 runs
  each, **576 in all**, on llama.cpp `b10644-d7a207411`. The reading is the
  [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) lineup addendum, with the
  selection consequence at [ADR-0004](../../adr/ADR-0004-model-lineup.md), the engine half at
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)'s lineup section and the operator half in the
  subagent runbook. **The repair does not generalise, because the defect does not.** On the roster
  alternate the bare envelope answers a summarization on 30 of 32 where the default pick answers on
  9, so there was no narration there to take back; the sentence still helps it overall, 76 of 96 to
  83 of 96, but on the extraction shape rather than the summarization one, and the intervals overlap
  enough that the honest claim is a small help and certainly not a cost. **The third outcome this
  entry named fired, on the other pick.** gemma-4-E2B is worse with the sentence than without it
  taken over all three shapes, 84 of 96 against 90 of 96: it recovers the narrating shape completely,
  27 of 32 to 32 of 32, and loses an extraction from 32 to 28 and a one-fact lookup from 31 to 24.
  Nothing shipped stands on it, the default and the roster alternate both being on the paying side,
  but one `CORTEX_MODEL_FILE_SUBAGENT` reaches it and nothing warned.
  Two mechanisms behind that, both counted as rates over draws. The reasoning residue is **0 of 96
  on the roster alternate**, on every arm and every shape, against 8 of 96 on the default pick and
  **14 of 96 on the E2B**, which is exactly the order the ADR-0005 lineup section's template column
  put the three picks in before any of this was decoded, so that column is now a rate and not only a
  rendering. And the roster alternate's own failures are a different thing entirely: no trace at all,
  10 capped runs that are a degenerate repetition inside `reply`, and **8 of its 13 constrained
  non-deliveries still `ok=True`**, so the instruction addendum's "not one failed quietly" is the
  default pick's reading and not the tier's.
  Opened by it: [R-482](482-the-sentence-is-one-wording-for-every-entry.md), the remedy, and
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), the three entries of this tier that were
  not reached tonight. [R-480](480-a-narrated-reply-arrives-as-an-answer.md) is amended rather than
  reopened: its trigger was written as an answer rate, and the answer rate turns out not to predict
  the quiet failures it stands for.
