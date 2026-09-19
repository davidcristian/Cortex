# The tier's reasoning-off flag worked on every run until a firmer prompt pushed on it

**Status:** done 2026-08-29
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

Every subagent server this repo starts uses `--chat-template-kwargs '{"enable_thinking": false}'`
beside `--reasoning-budget 0`, and ADR-0049 treats the budget as the one that reaches a request
with a `response_format`, where the kwarg was measured not to. That was true on 160 of the 160 runs
the answer measurement took at the harness's own instruction: not one reasoning character on any of
four request shapes.

On 40 further runs of the same server in the same session, differing only in a firmer subtask
wording, 3 wrote 2282 to 3692 characters into the reasoning channel, which a delegated run drops
unread. All three are on one body. Two are ordinary deliberation; the third put a whole summary in
the reasoning channel and a second, different summary in `reply`, where the cap cut it. Two of the
three were lost runs, cut at 1024 and refused.

## History

- 2026-08-28: opened by the close of [R-459](459-what-the-envelope-costs-the-answer.md), on three
  draws in forty, all on one body, under a probe instruction that had not been decided on.
- 2026-08-28: the instruction was decided and shipped
  ([R-476](476-the-envelopes-answer-rate-is-an-instruction.md)), and its re-measurement gave this
  entry three things without closing it. A rate: 8 of 96 constrained draws against 1 of 96 with the
  sentence removed and 0 of 96 unconstrained, so the opening exists without the prompt pushing on it
  and the push makes it about eight times as likely. More than one body and one shape: the eight
  fall on two of the four report bodies and on all three subtask shapes, including a one-fact lookup
  whose whole answer is two words. And a mechanism: six of the eight are not deliberation at all.
  They open with a malformed channel marker, the literal `t</c>`, `t <|channe|s_input>`, `h</c>` or
  `t</channe|c>`, and then write the answer itself into the reasoning channel, running to the cap
  and coming back refused. That is a control token the model had no business emitting being parsed
  as a channel switch. Read in full in ADR-0028.
- 2026-08-29: closed by ADR-0049, which re-measured the cell on a server using both flags and wrote
  the sentence into the two documents that stated the claim without one. The entry is right, at
  eight times its own sample: 13 draws in 76 of the exact request a delegated run sends wrote 1582
  to 4078 characters into the reasoning channel and 8 returned an empty reply cut at the cap, on two
  of the four bodies. The per-request value shipped that day is not the repair here: it is declined
  for the delegated path by decision, it would be the same sampler zero the flag already sets, and
  20 draws sending it on top of both flags still produced one. And the mechanism is the opposite of
  this entry's hypothesis: an unflagged twin of the same server deliberated on 8 draws of 8 in
  ordinary, well formed prose and on 0 of 8 with the key, where 11 of the flagged server's 13 traces
  open with a garbled channel marker, so the budget is applied and its forced close is mis-parsed
  rather than being overruled by a grammar. Two corrections on the way past:
  `test_thinking_switch_live.py` cannot take the cell this entry names, its control asserting that
  the no-switch run deliberated, and the runbook already had the sentence this entry says all three
  documents owe. What the close leaves is the attribution and a probe that reproduces it,
  [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md).
