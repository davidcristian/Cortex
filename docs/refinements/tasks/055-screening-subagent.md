# Screening subagent for external content

**Status:** declined 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

A small subagent that would screen external content for injection markers before the cortex sees
it.

The entry's own reason for calling it pointless stopped being true two days after it was written.
It reported the 2026-07-01 matrix, in which Qwen3.5-2B and Qwen3.5-9B repeated the injected
instruction under the shipped framing. On 2026-07-03 the subagent pick moved to gemma-4-E4B on
exactly that axis, at 0 of 10 obeyed when framed against the earlier pick's 1 of 10, and
[roster.py](../../../brain/packages/core/src/cortex_core/roster.py) forces that model on any
tainted or tool-enabled spawn.

The decline rests on something else: the screener's answer has no consumer. Every deterministic
consumer of untrusted provenance keys on a bit that `TaintLedger.observe` sets from `result.trust`
alone, before any judgement about the content
([untrusted.py](../../../brain/packages/core/src/cortex_core/untrusted.py)). The dispatcher denies
a call needing approval on `stamp.tainted` before the confirmer is consulted
([dispatch.py](../../../brain/packages/core/src/cortex_core/dispatch.py)),
`ConfirmFreeToolRegistry` removes such a tool from a subagent's registry rather than denying it later
([aggregate.py](../../../brain/packages/core/src/cortex_core/aggregate.py)), `record_exchange`
suppresses or marks the memory write
([turn_output.py](../../../brain/packages/core/src/cortex_core/turn_output.py)), and the guardrail
widens its grounds on taint and on opacity
([guardrail.py](../../../brain/packages/core/src/cortex_core/guardrail.py)).

A screener can do one of two things with its answer. It can refuse a read, which is a judgement
about what a passage means made over attacker-controlled text, the same form the footer heuristics
were declined on. Or it can clear the taint bit so those four consumers no longer apply, which
turns a fail-closed deterministic boundary into a small model's opinion. Neither is buildable, and
a screener that changes nothing is a model load per read that buys nothing.

The trigger the origin named has been read five times and has never fired anywhere a screener
could act. Framing works on the cortex, fails on the two Qwen sizes the pick then dropped, holds
at 0 of 10 on the brain tier, holds at 0 of 10 in the replayed-quotation variant, and leaks on the
pixel variant at 1 to 2 of 30 framed against 5 of 30 unframed. The one remaining leak is therefore
the channel a text screener cannot read at all, and the answer already recorded for pixels is
deterministic: the `opaque` bit drops the memory write outright and moves the guardrail to its
strictest setting, with pixel-level redaction in the body recorded as
[R-269](269-pixel-level-screening.md).

It reopens on one thing: a measured case of the cortex obeying an instruction through fenced text
that the deterministic checks do not already stop, at which point the answer is a preamble clause,
since a clause is what moved every previous cell of these matrices.

## History

- 2026-08-16: Declined and recorded as ADR-0013 decision 6. The origin had recorded a trigger all
  along ("only if host validation shows framing too leaky") that this file lost in transcription.
