# The constrained shape answers one time in four, and the repair is a sentence nothing writes

**Status:** landed 2026-08-28
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-08-28 by the close of
[R-459](459-what-the-envelope-costs-the-answer.md), which priced the reply envelope as an answer for
the first time and found the price is the answer itself.

A subagents-only stack hands its subagents no dispatcher, so every reply is decoded into
`REPLY_ENVELOPE` ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)). Measured over
four report bodies at ten draws each on the shipped pick, that shape delivers a summary on **10 of
40** draws where the unconstrained shape delivers on 40 of 40. The other thirty replies are the
model narrating the task: a plan, a restatement of the instruction, or one sentence announcing the
summary it never writes. When it does answer, the answer is as good as raw, so what the envelope
costs is arrival rather than quality. The whole reading is the ADR-0005 answer addendum.

**The two repairs that live in the schema are measured and neither works.** A `description` on the
`reply` property moved it to 9 of 40, and a required `notes` field ahead of `reply` for the
narration to occupy moved it to 10 of 40, the model narrating into both fields. The reason is one
reading and it rules out the whole family: this build shows the model **no part of a
`response_format`**, rendering a byte-identical prompt with the envelope and without it, so a schema
constrains the next token and never describes a contract.

**The repair that works is the subtask text**, which is the only channel that reaches the model.
Appending "Your entire response must be the summary itself. Do not describe the task, plan an
approach, or announce what you are about to write." to the same instruction, same bodies, same
grammar, same cap, delivers **39 of 40**.

**Why it was left.** The probe is a prompt, and what ships would be a change to what the subagent
contract *says*, written into the runner beside the constraint rather than into a measurement
harness. That is an ADR-0028 decision about the contract of a delegated run, not a line to type at
the end of a measurement, and it has a residue that has to be designed around rather than accepted:
three of those forty draws, all on one body, moved 2282 to 3692 characters into the reasoning
channel that a delegated run drops unread, on a server carrying both reasoning-off flags. Those
three are the only draws above 323 decoded tokens; one finished at 912 and two reached the 1024 cap
and came back refused, and one of those two had written a whole summary into the reasoning channel
before writing a second one into `reply`. So the instruction that recovers the answer also buys a
new way to lose one, at about one draw in thirteen, and whether the flag or the wording owns that is
[R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md).

**What would close it.** A decision recorded at
[ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) about where the sentence lives and
what it says, then the ordinary slice: the wording as a module constant beside `REPLY_ENVELOPE`,
applied on the constrained path only, unit-gated for the composition (a constrained attempt's
messages carry it, an unconstrained one's do not), and re-measured through
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`, whose `CORTEX_ENVELOPE_INSTRUCTION`
knob exists for exactly this. Two things the re-measurement owes that tonight's did not:

- **More than one subtask shape.** Everything above is summarization, which is the shape that
  invites deliberation and therefore the shape the effect lives on. An extraction and a lookup are
  in the same tier's measured repertoire and neither has been asked, and a wording tuned on
  summarization alone could easily cost a shape that was never narrating.
- **The trace residue counted.** The reasoning channel is where the recovered narration went, so the
  candidate wording has to be read for how often it does that as well as for how often it answers,
  and both are rates over draws rather than cells.

Worth deciding at the same time, since the answer changes the wording: whether a plan that arrives
in `reply` should be treated as a failed run at all. Today it is `ok=True` and the cortex is handed
a sentence about summarizing as though it were a summary, which is the quietest of the failures
here.

## Trail

- 2026-08-28: opened by the close of
  [R-459](459-what-the-envelope-costs-the-answer.md), which measured the constrained niche answering
  one time in four and declined to type a repair that is a decision about the subagent contract.
- 2026-08-28: Landed. The decision is the
  [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) instruction addendum, in five
  parts: the sentence lives beside the grammar in `cortex_core/subagent_reply.py` as
  `REPLY_INSTRUCTION` and `instruct_reply`, it is appended last to the instruction, it names the
  answer rather than a genre, it rides with `CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT` and gets no knob of
  its own, and **a plan that still arrives in `reply` is deliberately not detected**, since no
  detector over prose can separate a plan from an answer and a false positive destroys an answer the
  cortex had. `task_messages(task, *, constrain)` is the composition and three unit tests in
  `test_runner.py` gate it.
  Re-measured through the committed harness on the shipped pick at `-ngl 99`, three arms over four
  report bodies at eight draws each and **three subtask shapes rather than one**, a summarization,
  an extraction and a one-fact lookup: **288 runs**. The envelope with the sentence answers **90 of
  96** against **72 of 96** without it, and the whole of the gap is the shape that narrates, 29 of
  32 against 9 of 32, the bare arm reproducing this entry's own 10 of 40. The two shapes that never
  narrated cost a draw each, 31 and 30 of 32 against 32 and 31.
  Both of the readings this entry demanded that its predecessor's did not: the other shapes are
  asked, and the residue is a rate. **8 of 96 constrained draws** wrote into the reasoning channel
  against 1 of 96 bare and 0 of 96 raw, on two bodies and all three shapes, and six of the eight are
  not deliberation but a malformed channel marker followed by the answer itself routed to the half a
  delegated run drops. That belongs to
  [R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md), which now has a rate, more than
  one body and a mechanism.
  The finding that settles the detector question is the failure **kind**: of the bare arm's 24 non
  deliveries, 23 came back `ok=True`, and of the constrained arm's 6, all 6 came back refused. The
  sentence moves the residue out of the silent failure mode.
  Opened by it: [R-480](480-a-narrated-reply-arrives-as-an-answer.md), which carries the quiet
  failure this close decided not to detect, and
  [R-481](481-the-sentence-is-measured-on-one-pick.md), which carries what 288 runs of one model
  cannot say about the roster's other one.
