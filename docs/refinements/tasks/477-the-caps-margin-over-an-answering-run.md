# The token cap has 12% of headroom over a delegated answer that is doing its job

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a delegated summary cut at the cap on a subagents-only stack, or any change to what a
constrained subagent is told, since the reply lengths this entry is about are a property of the
instruction rather than of the grammar.

Opened 2026-08-28 by the close of
[R-457](457-the-caps-derivation-on-the-shape-that-ships.md), which confirmed
`DEFAULT_SUBAGENT_MAX_TOKENS` where it stands and named the one number that argues the other way.
The instruction its trigger turns on is
[R-476](476-the-envelopes-answer-rate-is-an-instruction.md).

At the instruction the measurement harness has always sent, the shipped tool-less shape answers in
256 to 429 decoded tokens, so 1024 has room to spare. Under the instruction that actually makes that
shape answer, four bodies at ten draws, 38 of 40 runs land between 248 and 323 tokens and the
remaining two are the interesting ones: **one finished a correct, complete summary at 912 decoded
tokens, and two were cut at 1024 and came back refused.** So on the shape that would ship if R-476
lands, the cap sits about 12% above a real answer and fires on 5% of draws.

**Why it was left.** Retuning against a distribution measured under a probe instruction is the same
mistake this entry's parent refused twice: the cap was once derived from a shape nothing shipped,
and it declined to be re-derived from a reply nobody would accept. A cap sized to an instruction
that has not been decided on yet is the third version of it. The two cut runs are also not obviously
answers being truncated: they spent 3351 and 3692 characters in the reasoning channel that a
delegated run drops unread, so what the cap cut may be a trace rather than a summary, and which of
those two it is decides whether the repair is a bigger cap or a quieter tier.

**What would close it.** Re-read the same distribution once the constrained instruction is settled,
at the same four bodies and at least ten draws, and separate the two populations before touching the
number: a run whose decoded tokens went to `reply` and a run whose tokens went to the reasoning
channel are different failures and only the first argues for more room. If the answering tail really
does reach 900 tokens with no trace under it, the honest options are a cap above it or an
instruction that shortens the answer, and both are cheaper than they look because the run deadline
already bounds a runaway in the other unit: on an idle host it admits about 3200 decoded tokens, so
there is room between 1024 and that to grow into. On a saturated host there is none, which is
[R-478](478-two-ceilings-on-one-run-and-no-ordering.md) and is the reason this entry's answer cannot
be a single number for both.
