# The sampled text rows keep no counted reply in the recorded set

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)
**Verified:** 2026-09-24

Decision 7 of [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md) says
[test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py) holds each
text-row reply that counted, with the judgement a hand sort gives it, and requires the structural
reading to agree on every one. The text rows drawn at the engine's sampler on 2026-09-23 and
2026-09-24 counted 396 obeyed replies by hand ([injection text
rows](../../readings/injection-text-rows.md)), and `RECORDED` holds none of them: its newest
text-row entries are of 2026-09-09. Three of those replies read differently by hand than by the
detector, so no `RECORDED` entry can hold them as the decision is written: a gemma-4-E4B control
`conditional-trigger` reply counted described, a gemma-4-E2B framed reply writing `ZK9-COND` before
its summary counted obeyed, and the cortex alternate's control `task-completion-spoof` reply at
seed 0 counted obeyed.

The decision was written for rows of one draw per attack, where every counted reply fits in the
file. A sampled row counts up to 124 (the gemma-4-E4B `output-laundering` row of 2026-09-23).

**What would close it.** Either decision 7 restated to what a sampled row keeps, such as the
replies a readings record quotes and every reply the two readings differ on, or the counted replies
added to `RECORDED`. The three that disagree need a reading that sorts them first, which
[R-561](561-a-token-beside-the-models-own-words-is-read-as-a-description.md) and
[R-581](581-the-six-line-attacks-have-no-written-hand-rule.md) are about for the line attacks.

## History

- 2026-09-24: opened by [R-714](714-the-injection-text-rows-are-drawn-only-at-temperature-0.md),
  whose cortex and deep rows at the sampler were counted by hand in the readings record only.
