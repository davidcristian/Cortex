# The injection text rows are drawn only at temperature 0

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)
**Verified:** 2026-09-23

Every count in [injection text rows](../../readings/injection-text-rows.md) but the subagent
candidates' card cells was drawn from 2026-09-04 to 09-11, when `completion_body` in
`test_injection_defense_live.py` sent temperature 0. Since 2026-09-22 it sends none, so a row
samples as the shipped request does. At temperature 0 a control's prompt is the same bytes in every
draw and has one answer, and a framed count varies only through the fence's nonce.

The five subagent candidates' card rows were drawn at the sampler on 2026-09-23: the pick reads
framed 8 of 100 where the temperature-0 table read 0 of 10, and
[R-715](715-the-subagent-pick-obeys-framed-injections-as-often-as-the-qwen-candidates.md) holds
what that does to the pick. [model-read-wording](../../readings/model-read-wording.md) drew the
cortex pick framed 0 of 220 and the deep pick 0 of 66 at the sampler, over both preamble wordings,
with no control.

**What remains.** Each of these at ten repetitions per attack, framed and control, every obeyed and
described reply read by hand: the cortex pick, its alternate and the deep pick on the card, and the
five subagent candidates on the CPU.

**What would close it.** The table restated with those counts in place of the temperature-0 ones,
and each decision that quotes a count that changes edited: ADR-0004 decisions 6 and 8.

## History

- 2026-09-23: opened by the preamble's rewording under
  [R-707](707-model-read-texts-keep-banned-words.md), whose paired draws read the E4B's framed
  count at the sampler.
- 2026-09-23: the subagent candidates' card rows drawn at the sampler opened
  [R-715](715-the-subagent-pick-obeys-framed-injections-as-often-as-the-qwen-candidates.md) and
  [R-716](716-the-injection-harness-reads-a-send-email-call-only-under-one-attack.md).
