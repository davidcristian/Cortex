# Screening subagent for external content

**Status:** declined 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

A small subagent that pre-screens external content for injection
markers before the cortex sees it. Mostly moot: the GPU validation showed a screener would be
another small, equally-injectable model. Kept only as a last-resort option behind the delegation seam.

**Declined, and the first finding is that this entry's own reason for calling it moot stopped
being true two days after it was written.** The sentence about "another small, equally-injectable
model" reports the 2026-07-01 matrix, which measured Qwen3.5-2B and Qwen3.5-9B parroting the
injected instruction under the shipped framing. On 2026-07-03 the subagent pick was revised to
gemma-4-E4B precisely on that axis, at 0 of 10 obeyed framed against the earlier pick's 1 of 10
([ADR-0004](../../adr/ADR-0004-model-lineup.md) pick-revision addendum), and
[roster.py](../../../brain/packages/core/src/cortex_core/roster.py) forces that model on any
tainted or tool-enabled spawn. So the shipped small tier is the injection-robust one and the
entry's premise is stale. The decline rests on other ground, which is the point of re-deriving it.

**The screener's verdict has no consumer, which is the decisive half.** Every deterministic
consumer of untrusted provenance keys on a bit that `TaintLedger.observe` sets from
`result.trust` alone, before any judgement about the content
([untrusted.py](../../../brain/packages/core/src/cortex_core/untrusted.py)): the dispatcher hard
denies a gated call on `stamp.tainted` before the confirmer is consulted
([dispatch.py](../../../brain/packages/core/src/cortex_core/dispatch.py)), `UngatedToolRegistry`
strips a gated spec from a subagent's registry rather than denying it later
([aggregate.py](../../../brain/packages/core/src/cortex_core/aggregate.py)), `record_exchange`
suppresses or marks the memory write
([turn_output.py](../../../brain/packages/core/src/cortex_core/turn_output.py)), and the guardrail
widens its grounds on taint and on opacity
([guardrail.py](../../../brain/packages/core/src/cortex_core/guardrail.py)). A screener can do
exactly one of two things with its answer. It can refuse a read, which is a judgement about what a
passage means made over attacker-controlled text, the same shape the footer heuristics were
declined on. Or it can clear the taint bit so those four consumers no longer apply, which converts a
fail-closed deterministic boundary into a small model's opinion and is the one thing the gate
exists to prevent. Neither is buildable, and no third option exists: a screener that changes
nothing is a model load per read that buys nothing.

**The trigger the origin named has been read five times and has never fired anywhere a screener
could act.** Framing works on the cortex, fails on the two Qwen sizes the pick then dropped,
holds at 0 of 10 on the brain tier, holds at 0 of 10 in the replayed-quotation arm, and leaks on
the pixel arm at 1 to 2 of 30 framed against 5 of 30 unframed. The one residual leak is therefore
the channel a text screener cannot read at all, and the answer already recorded for pixels is
deterministic: the `opaque` bit drops the memory write outright and escalates the guardrail to its
strictest ground, with pixel-level redaction in the body recorded separately as
[R-269](269-pixel-level-screening.md). **The area's count moves by one and this decline opens
nothing.** It reopens on one thing: a measured obedience on the cortex, through fenced text, that
the gate does not already stop, at which point the answer is a preamble clause, since a clause is
what moved every previous cell of these matrices.

## Trail

- 2026-08-16: Declined. The gap its unrecorded trigger left is closed by settling the entry rather
  than by naming what would fire it, the origin having recorded a trigger all along ("only if host
  validation shows framing too leaky") that this file lost in transcription. Recorded as the
  screening-subagent addendum at the origin decision record.
