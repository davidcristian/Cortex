# The tier's reasoning-off flag held on every run until a firmer prompt pushed on it

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-28 by the close of
[R-459](459-what-the-envelope-costs-the-answer.md), whose measurement produced the first draws in
this repo where a server carrying both reasoning-off flags deliberated anyway.

Every subagent server this repo starts carries `--chat-template-kwargs '{"enable_thinking": false}'`
beside `--reasoning-budget 0`, and the ADR-0005 thinking-lever addendum records the budget as the
lever that reaches a request carrying a `response_format`, where the kwarg was measured not to. That
holds on 160 of the 160 runs the answer measurement took at the harness's own instruction: not one
reasoning character on any of four request shapes.

On 40 further runs of the same server in the same session, differing only in a firmer subtask
wording, **3 wrote 2282 to 3692 characters into the reasoning channel**, which a delegated run drops
unread. All three are on one body. Two are an ordinary deliberation; the third put a whole summary
in the reasoning channel and a second, different summary in `reply`, where the cap cut it. Two of
the three were lost runs: cut at 1024 and refused.

Read against what the tree already knows, this is plausible rather than surprising, which is why it
is worth measuring rather than dismissing. The mechanism section of the ADR-0005 switch-is-advisory
addendum found that llama.cpp's gemma-4 handler does not force a thought open under a grammar, it
**holds** it open as the only continuation that admits prose. If a firmer instruction is what stops
prose from being admissible inside `reply`, then the door that handler leaves open is exactly where
the prose goes, and a budget of zero would be one more thing the grammar outranks. That is a
hypothesis and not a reading.

**Why it was left.** Three draws on one body under one probe instruction, and the instruction itself
is undecided ([R-476](476-the-envelopes-answer-rate-is-an-instruction.md)). The claim it would
amend is stated in three places, the compose override's command block,
[ADR-0010](../../adr/ADR-0010-subagents.md) and the thinking-lever addendum, and amending a shipped
claim on three draws is the mistake the sibling entries around this one were opened to refuse.

**What would close it.** The committed probe
(`brain/packages/inference/tests/test_thinking_switch_live.py`) already draws each cell several
times against a server whose flags the operator chooses, so this is a cell it does not yet have: the
constrained shape, on a server carrying **both** reasoning-off flags, against a prompt firm enough
to forbid prose in the reply, at the same repeat count as its neighbours and over more than the one
body that produced these three. Two outcomes are worth acting on. A rate that survives repeats means
the reasoning-off pair is conditional on the prompt as well as on the request shape, and the compose
comment, ADR-0010 and the runbook all owe that sentence. A rate that vanishes means these three were
one body's quirk and the record here is the entry that says so.

Worth reading beside it: [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), since
the per-request `reasoning_budget_tokens` this build honours is a second lever on the same shape and
would be the obvious repair if the flag really is conditional.
