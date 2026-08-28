# The sentence every constrained subagent now carries is measured on one pick

**Status:** open, actionable
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
