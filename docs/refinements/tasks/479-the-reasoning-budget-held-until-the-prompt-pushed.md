# The tier's reasoning-off flag held on every run until a firmer prompt pushed on it

**Status:** landed 2026-08-29
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
prose from being admissible inside `reply`, then the opening that handler leaves is exactly where
the prose goes, and a budget of zero would be one more thing the grammar outranks. That is a
hypothesis and not a reading.

**Why it was left.** Three draws on one body under one probe instruction, and the instruction itself
is undecided ([R-476](476-the-envelopes-answer-rate-is-an-instruction.md)). The claim it would
amend is stated in three places, the compose override's command block,
[ADR-0010](../../adr/ADR-0010-subagents.md) and the thinking-lever addendum, and amending a shipped
claim on three draws is the mistake the sibling entries around this one were opened to prevent.

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

## Trail

- 2026-08-28: opened by the close of
  [R-459](459-what-the-envelope-costs-the-answer.md), on three draws in forty, all on one body,
  under a probe instruction that had not been decided on.
- 2026-08-28: the instruction was decided and shipped
  ([R-476](476-the-envelopes-answer-rate-is-an-instruction.md)), and its re-measurement gives this
  entry three things it was waiting for without closing it. **A rate**: 8 of 96 constrained draws
  against 1 of 96 with the sentence stripped and 0 of 96 unconstrained, so the opening exists without
  the prompt pushing on it and the push makes it about eight times as likely. **More than one body
  and more than one shape**: the eight fall on two of the four report bodies and on all three
  subtask shapes, including a one-fact lookup whose whole answer is two words, so these are not one
  body's quirk. **A mechanism worth checking against the handler**: six of the eight are not
  deliberation at all. They open with a malformed channel marker, the literal `t</c>`,
  `t <|channe|s_input>`, `h</c>` or `t</channe|c>`, and then write the answer itself into the
  reasoning channel, running to the cap and coming back refused. That is a control token the model
  had no business emitting being parsed as a channel switch, which is a narrower claim than "the
  budget did not hold" and points the committed probe at a cell it can actually distinguish: the
  same prompt against a build whose gemma-4 handler treats an unopened thought differently. Read in
  full in the ADR-0005 instruction addendum.
- 2026-08-29: **landed** by the ADR-0005 firm-prompt addendum, which re-measured the cell on a
  server carrying both flags and wrote the sentence into the two documents that were still stating
  the claim without one. Three things it found. **The entry is right, at eight times its own
  sample**: 13 draws in 76 of the exact request a delegated run sends wrote 1582 to 4078 characters
  into the reasoning channel and 8 returned an empty reply cut at the cap, on two of the four
  bodies. **The per-request lever shipped that day is not the repair here**, which is why this
  entry is not declined the way [R-475](475-a-tier-can-be-asked-what-its-template-answers.md) was:
  it is declined for the delegated path by decision, it would be the same sampler zero the flag
  already set, and 20 draws carrying it on top of both flags still produced one. **And the
  mechanism is the opposite of this entry's hypothesis**: an unflagged twin of the same server
  deliberated on 8 draws of 8 in ordinary, well formed prose and on 0 of 8 with the key, where 11
  of the flagged server's 13 traces open with a garbled channel marker, so the budget is firing and
  having its forced close mis-parsed rather than being outranked by a grammar. Two corrections to this
  entry's own text on the way past: `test_thinking_switch_live.py` cannot take the cell it names,
  its control asserting that the no-switch arm deliberated, and the runbook already carried the
  sentence this entry says all three documents owe. What the close leaves is the attribution and a
  probe that reproduces it,
  [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md).
