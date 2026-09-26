# The joined system message is unmeasured on the Qwen alternates

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0071](../../adr/ADR-0071-leading-system-messages.md)
**Verified:** 2026-09-26

Where the leased server's template cannot take several leading system messages, the adapter sends
the security preamble, the recalled memory and the recap as one system message
([ADR-0071](../../adr/ADR-0071-leading-system-messages.md)). The two alternates that receive it
are Qwen3.5-9B for the cortex and Qwen3.6-27B for the deep tier, which gets it only when a turn has
all three. Before the join, Qwen3.5-9B answered no turn with a memory or a recap (HTTP 500).
Qwen3.6-27B read no recap on a turn that also recalled a memory, and otherwise merged the preamble
and the memory or the recap into one system turn itself, the same bytes the join sends; Qwen3.8
merges every leading one the same way. No framing reading covers this layout on any of them.

The joined message is the one the preamble calls "this system message" and lets direct the model.
The fenced memory and the recap keep their fences, but the trusted memory lines, which include
earlier assistant replies, sit inside it unfenced.

The injection harness (`test_injection_defense_live.py`) sends one system message, and the recap
preface rows in `test_model_read_wording_live.py` send two and are drawn only on the gemma picks
([model-read wording](../../readings/model-read-wording.md)). R-740 covers the recall judge and
the recap fold on the Qwen deep candidates, which are separate calls; this entry is the reply's own
prompt.

What would close it: the recap preface's attack rows, one fenced-memory attack row and one row
whose trusted memory has an assistant half quoting an injection, drawn on each alternate through
the adapter's joined request against the unframed control, with the count to beat written here
before the draw.

## History

- 2026-09-26: filed by the join of leading system messages.
