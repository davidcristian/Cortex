# The constrained shape answers one time in four, and the repair is a sentence nothing writes

**Status:** open, actionable
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
