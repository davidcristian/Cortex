# The token cap has 12% of headroom over a delegated answer that is doing its job

**Status:** declined 2026-09-11
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-28 by the close of
[R-457](457-the-caps-derivation-on-the-shape-that-ships.md), which confirmed
`DEFAULT_SUBAGENT_MAX_TOKENS` where it stands and named the one number that argues the other way.
The instruction it waited on, [R-476](476-the-envelopes-answer-rate-is-an-instruction.md), landed
the same day, so this entry is work somebody can pick up rather than a deferral.

At the instruction the measurement harness has always sent, the shipped tool-less shape answers in
256 to 429 decoded tokens, so 1024 has room to spare. Under the probe instruction that made that
shape answer, four bodies at ten draws, 38 of 40 runs land between 248 and 323 tokens and the
remaining two are the interesting ones: **one finished a correct, complete summary at 912 decoded
tokens, and two were cut at 1024 and came back refused.** So on that shape the cap sits about 12%
above a real answer and fires on 5% of draws.

**What that distribution is not is the shipped one.** The sentence that ships is `REPLY_INSTRUCTION`
in `cortex_core/subagent_reply.py`, appended by `instruct_reply` on the constrained path alone, and
it names the answer where the probe named the summary. The re-measurement that landed it read 288
runs over three subtask shapes and published rates rather than token bands: the envelope with the
sentence answers 90 of 96 against 72 without it, and 8 of 96 constrained draws wrote into the
reasoning channel. So what the cap has never been read against is the wording a subagent is
actually sent.

**Why it was left, and why that reason has expired.** Retuning against a distribution measured under
a probe instruction is the same mistake this entry's parent declined twice: the cap was once derived
from a shape nothing shipped, and it declined to be re-derived from a reply nobody would accept. A
cap sized to an instruction that had not been decided on yet was the third version of it, and that
was the whole of why this waited. The decision has since been recorded and the wording shipped, so
the distribution can be read on it. The two cut runs are also not obviously answers being truncated:
they spent 3351 and 3692 characters in the reasoning channel that a delegated run drops unread, so
what the cap cut may be a trace rather than a summary, and which of those two it is decides whether
the repair is a bigger cap or a quieter tier.

**What would close it.** Re-read the distribution on the shipped sentence, at the same four bodies
and at least ten draws, and separate the two populations before touching the
number: a run whose decoded tokens went to `reply` and a run whose tokens went to the reasoning
channel are different failures and only the first argues for more room. If the answering tail really
does reach 900 tokens with no trace under it, the honest options are a cap above it or an
instruction that shortens the answer, and both are cheaper than they look because the run deadline
already bounds a runaway in the other unit: on an idle host it admits about 3200 decoded tokens, so
there is room between 1024 and that to grow into. On a saturated host there is none, which is
[R-478](478-two-ceilings-on-one-run-and-no-ordering.md) and is the reason this entry's answer cannot
be a single number for both.

## Trail

- 2026-09-09: **The trigger fired the day this was written and nobody moved the status.** Its second
  clause is any change to what a constrained subagent is told, and the instruction landed on
  2026-08-28, hours after this entry was opened, as `REPLY_INSTRUCTION` in
  `cortex_core/subagent_reply.py`. The shipped wording is not the probe wording the 912-token draw
  was measured under, so the distribution this entry is about has never been read on the shape that
  ships. Every number here still holds against the ceilings addendum: 1024 in
  `cortex_core/subagents.py`, 38 of 40 inside 248 to 323, one finished answer at 912, two cut at the
  cap, and 3351 and 3692 characters of reasoning under those two.
- 2026-09-11: **Declined, on the reading it asked for, which says the long answer was a trace.**
  The distribution was re-read on the shipped wording at this entry's own conditions, the same four
  bodies at ten draws, through `test_envelope_cost_live.py` with the `constrained` arm alone, so the
  sentence on the wire was the one `instruct_reply` appends, on the E4B pick at `-ngl 99` on
  llama.cpp `b10680-d7bd3bfca` (40 runs, 95.65 s, decode 115 to 148 tok/s). The two populations
  separate and neither argues for more room. 39 of 40 runs delivered a summary under
  `scripts/envelopejudges.py` at the floor's own readings, and every one of those 39 replies is
  **250 to 373 decoded tokens** (906 to 1340 characters, median 278), so the longest answer this tier
  writes under the shipped sentence is 36% of the cap. The one run that finished at 904 decoded
  tokens wrote 2320 characters of a thinking process into the reasoning channel first and then a
  1003-character reply inside that band, and the one run cut at 1024 wrote 3079 characters into
  that channel and nothing into `reply`. The 912-token draw this entry was opened on had the same
  shape: [R-476](476-the-envelopes-answer-rate-is-an-instruction.md) records it among the three
  draws that moved 2282 to 3692 characters into the reasoning channel, so the 12% in this title was
  headroom over a trace and an answer counted together, and the ceilings addendum's sentence calling
  912 a finished answer at 89% of the cap is corrected in the ADR-0005 margin addendum. What reaches
  the cap on the shipped wording is the residue the instruction addendum counted, 2 of 40 here
  against its 8 of 96, and neither a bigger cap nor a shorter instruction would move it. The cap
  stays at 1024. The sitting's box state and the full table are in that addendum.
