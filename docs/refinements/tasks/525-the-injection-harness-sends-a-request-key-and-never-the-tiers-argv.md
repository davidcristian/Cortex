# The injection harness sends a request key, and never the tier's argv

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-02 by the close of
[R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), which owed an injection arm
for a flag change and drew the harness's corpus by hand because the harness cannot take one.

`brain/packages/inference/tests/test_injection_defense_live.py` starts every server with `-ngl 99
--ctx-size 8192 --parallel 1 --jinja` and no reasoning flag, and its `_post` sends
`chat_template_kwargs: {"enable_thinking": false}` on every request of a thinking-off row. So the
subagent rows of ADR-0004's injection table, the E4B pick's 0 of 10 among them, measured the
rendering the request key produces. On a plain request that is the same prompt the shipped kwarg
renders, but it reaches the model by a route the shipped stack never takes: every subagent server
this repo starts carries the pair on its argv and `PlacedAttempt` sends no key. A build on which the
request key and the server flag part ways, which the deprecation
[R-461](461-the-tiers-thinking-flag-is-deprecated.md) records makes possible, would move the
harness's number without moving the tier's, and nothing would say so.

**Measured 2026-09-02 by hand**, the harness's own corpus and detectors against three gemma-4-E4B
servers on `b10680-d7bd3bfca`: the shipped pair with no request key, `--reasoning-budget 0` alone
with no request key, and the harness's own cell, no flag and the request key. Framed obedience was
0 of 10 on all three, three repeats each, and the unframed controls obeyed 1 to 2 of 10. So nothing
separates today, and the harness still cannot say so itself.

**What would close it.** A knob that starts the harness's server with extra argv, the shape
`_server` already assembles, and a `Model` field or a second knob that leaves the request key off,
so the shipped subagent row can be drawn as the stack sends it. The table's rows then say which
lever each measured. The hand run above is the reading to reproduce first.

## Trail

- 2026-09-02: opened by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), which needed the shipped
  argv on the harness's server and found it could only be sent by hand.
