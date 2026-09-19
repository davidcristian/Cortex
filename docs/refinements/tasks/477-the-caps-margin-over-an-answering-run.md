# The token cap has 12% of headroom over a delegated answer that is doing its job

**Status:** declined 2026-09-11
**Area:** subagents
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

At the instruction the measurement harness had always sent, the shipped tool-less shape answers in
256 to 429 decoded tokens, so 1024 has room to spare. Under the probe instruction that made that
shape answer, four bodies at ten draws, 38 of 40 runs fall between 248 and 323 tokens and the
remaining two are the interesting ones: one finished a correct, complete summary at 912 decoded
tokens, and two were cut at 1024 and came back refused. So on that shape the cap sat about 12% above
a real answer and fired on 5% of draws.

That distribution is not the shipped one. The sentence that ships is `REPLY_INSTRUCTION` in
`cortex_core/subagent_reply.py`, appended by `instruct_reply` on the constrained path alone, and it
names the answer where the probe named the summary. Closing this means re-reading the distribution
on the shipped sentence at the same four bodies and at least ten draws, separating a run whose
decoded tokens went to `reply` from one whose tokens went to the reasoning channel, since only the
first argues for more room.

## History

- 2026-08-28: opened by the close of
  [R-457](457-the-caps-derivation-on-the-shape-that-ships.md), which confirmed
  `DEFAULT_SUBAGENT_MAX_TOKENS` where it stands and named the one number that argues the other way.
- 2026-09-09: the trigger fired the day this was written and nobody moved the status. Its second
  clause is any change to what a constrained subagent is told, and the instruction was added on
  2026-08-28, hours after this entry was opened. Every number here still holds: 1024 in
  `cortex_core/subagents.py`, 38 of 40 inside 248 to 323, one finished answer at 912, two cut at the
  cap, and 3351 and 3692 characters of reasoning under those two.
- 2026-09-11: declined, on the reading it asked for, which says the long answer was a trace. The
  distribution was re-read on the shipped wording at this entry's own conditions, the same four
  bodies at ten draws, through `test_envelope_cost_live.py` with the `constrained` variant alone, on
  the E4B pick at `-ngl 99` on llama.cpp `b10680-d7bd3bfca` (40 runs, 95.65 s, decode 115 to 148
  tok/s). The two populations separate and neither argues for more room. 39 of 40 runs delivered a
  summary under `scripts/envelopejudges.py`, and every one of those 39 replies is 250 to 373 decoded
  tokens (906 to 1340 characters, median 278), so the longest answer this tier writes under the
  shipped sentence is 36% of the cap. The one run that finished at 904 decoded tokens wrote 2320
  characters of thinking into the reasoning channel first and then a 1003-character reply, and the
  one run cut at 1024 wrote 3079 characters into that channel and nothing into `reply`. The
  912-token draw this entry was opened on had the same shape, so the 12% in the title was headroom
  over a trace and an answer counted together, and ADR-0048 is corrected where it called 912 a
  finished answer at 89% of the cap. What reaches the cap on the shipped wording is the residue the
  instruction measurement counted, 2 of 40 here against its 8 of 96, and neither a bigger cap nor a
  shorter instruction would move it. The cap stays at 1024, and the box state and the full table are
  in the generation-bounds readings.
