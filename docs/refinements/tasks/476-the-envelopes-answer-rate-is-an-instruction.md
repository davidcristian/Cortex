# The constrained shape answers one time in four, and the repair is a sentence nothing writes

**Status:** done 2026-08-28
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

A subagents-only stack gives its subagents no dispatcher, so every reply is decoded into
`REPLY_ENVELOPE` ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)). Measured over
four report bodies at ten draws each on the shipped pick, that shape delivers a summary on 10 of 40
draws where the unconstrained shape delivers on 40 of 40. The other thirty replies are the model
narrating the task. When it does answer, the answer is as good as the unconstrained one, so what
the envelope costs is arrival rather than quality.

The two repairs that live in the schema were measured and neither works. A `description` on the
`reply` property moved it to 9 of 40, and a required `notes` field ahead of `reply` moved it to 10
of 40, the model narrating into both fields. One reading rules out the whole family: this build
shows the model no part of a `response_format`, rendering a byte-identical prompt with the envelope
and without it. The repair that works is the subtask text, the only channel that reaches the model.
Appending "Your entire response must be the summary itself. Do not describe the task, plan an
approach, or announce what you are about to write." to the same instruction, same bodies, same
grammar, same cap, delivers 39 of 40.

## History

- 2026-08-28: opened by the close of
  [R-459](459-what-the-envelope-costs-the-answer.md), which measured the constrained shape answering
  one time in four and declined to type a repair that is a decision about the subagent contract.
- 2026-08-28: closed as [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) decisions 5
  to 9, in five parts: the sentence lives beside the grammar in `cortex_core/subagent_reply.py` as
  `REPLY_INSTRUCTION` and `instruct_reply`, it is appended last to the instruction, it names the
  answer rather than a genre, it is sent with `CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT` and gets no
  setting of its own, and a plan that still arrives in `reply` is deliberately not detected, since
  no detector over prose can separate a plan from an answer and a false positive destroys an answer
  the cortex had. `task_messages(task, *, constrain)` is the composition and three unit tests in
  `test_runner.py` cover it. Re-measured through the committed harness on the shipped pick at
  `-ngl 99`, three variants over four report bodies at eight draws each and three subtask shapes,
  288 runs: the envelope with the sentence answers 90 of 96 against 72 of 96 without it, and the
  whole of the gap is the shape that narrates, 29 of 32 against 9 of 32, reproducing this entry's 10
  of 40. The two shapes that never narrated cost a draw each, 31 and 30 of 32 against 32 and 31. The
  residue is now a rate: 8 of 96 constrained draws wrote into the reasoning channel against 1 of 96
  bare and 0 of 96 unconstrained, on two bodies and all three shapes, and six of the eight are a
  malformed channel marker followed by the answer routed to the half a delegated run drops. That
  belongs to [R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md). The failure kind
  settles the detector question: of the bare variant's 24 non-deliveries, 23 came back `ok=True`,
  and of the constrained variant's 6, all 6 came back refused. Opened by it:
  [R-480](480-a-narrated-reply-arrives-as-an-answer.md) and
  [R-481](481-the-sentence-is-measured-on-one-pick.md).
