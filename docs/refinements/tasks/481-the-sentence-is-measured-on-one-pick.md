# The sentence every constrained subagent is now sent was measured on one pick

**Status:** done 2026-08-28
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

`REPLY_INSTRUCTION` is appended to the subtask of every tool-less subagent, whichever roster entry
runs it ([ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)). Every reading behind it is
gemma-4-E4B QAT q4_0, the default entry, on one llama.cpp build at one placement. The roster's
shipped alternate is Qwen3.5-2B Q4_K_M, from a different family with a different chat template and
a different reasoning switch, and it had never been asked whether the sentence helps it, does
nothing, or costs it.

The defect the sentence repairs is not a property of the wording. It is a property of a small model
meeting a grammar that admits prose and treating a plan as its whole output, and nothing measured
said another pick does the same thing at the same rate. The cost it brings is a property of the
tier's own machinery: the 8 draws in 96 that wrote the answer into the reasoning channel are on a
gemma template, six of them opening with a malformed channel marker.

## History

- 2026-08-28: opened by the close of
  [R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which shipped a sentence to every
  roster entry on 288 runs of one of them.
- 2026-08-28: closed. Two more subagent-tier entries were asked the same question through the same
  committed harness, the same four bodies, the same three subtask shapes, the same eight draws and
  the same `-ngl 99` substitution: the Qwen3.5-2B roster alternate and gemma-4-E2B, 288 runs each,
  576 in all, on llama.cpp `b10644-d7a207411`. The repair does not generalise, because the defect
  does not. On the roster alternate the bare envelope answers a summarization on 30 of 32 where the
  default pick answers on 9, so there was no narration to take back; the sentence still helps it
  overall, 76 of 96 to 83 of 96, but on the extraction shape, and the intervals overlap enough that
  the accurate claim is a small help and certainly not a cost. The third outcome this entry named
  happened on the other pick: gemma-4-E2B is worse with the sentence than without it over all three
  shapes, 84 of 96 against 90 of 96, recovering the narrating shape completely, 27 of 32 to 32 of
  32, and losing an extraction from 32 to 28 and a one-fact lookup from 31 to 24. Nothing shipped
  stands on it, but one `CORTEX_MODEL_FILE_SUBAGENT` reaches it and nothing warned. Two mechanisms
  behind that, both counted as rates over draws. The reasoning residue is 0 of 96 on the roster
  alternate, on every variant and shape, against 8 of 96 on the default pick and 14 of 96 on the
  E2B, which is the order the ADR-0005 lineup section's template column put the three picks in
  before any of this was decoded. And the roster alternate's own failures are a different thing: no
  trace at all, 10 capped runs that are a degenerate repetition inside `reply`, and 8 of its 13
  constrained non-deliveries still `ok=True`, so the reply-sentence change's claim that nothing
  failed quietly is the default pick's reading and not the tier's. The readings are the two-pick
  envelope review of 2026-08-28 at
  [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md), with the selection consequence at
  [ADR-0004](../../adr/ADR-0004-model-lineup.md), the engine half at
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)'s lineup section and the operator half in the
  subagent runbook. Opened by it:
  [R-482](482-the-sentence-is-one-wording-for-every-entry.md) and
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md).
  [R-480](480-a-narrated-reply-arrives-as-an-answer.md) is amended rather than reopened.
