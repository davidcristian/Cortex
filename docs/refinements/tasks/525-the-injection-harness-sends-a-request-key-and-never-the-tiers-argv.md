# The injection harness sends a request key, and never the tier's argv

**Status:** landed 2026-09-04
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
- 2026-09-04: **landed**. The premise held on the file as it stands after the image-budget and
  payload-size rows landed: `server_argv` took a `Budget` and nothing else, and `_post` sent
  `chat_template_kwargs` on every thinking-off request, so no row could be started with a tier's
  flags. A row now names a `Switch`, whose `argv` `server_argv` appends and whose `request_key`
  `completion_body` puts in the request, and the text arm runs once per entry in `SWITCHES`.
  Neither spelling is typed into the harness: `shipped_reasoning_off()` takes the pair off
  `ModelHostConfig`'s own subagent tier and `template_kwargs()` decodes that tier's flag into the
  request key, so the change needs no `crosscheck` entry and a renamed flag fails
  `test_switch_rows.py`, the CI-side gate on the two rows, instead of drifting. Measured over
  fifteen sittings on build `10680`: both gemma candidates drew identical cells under both
  switches in every sitting, the pick at 0 of 10 framed and 2 of 10 control; Qwen3.5-4B's
  `payload-splitting` cell fired once in four framed draws under each switch, which is the cell's
  own instability rather than the lever. The ADR-0004 switch-row addendum carries the table, the
  argv-reached-the-engine check and the correction to the E2B row. Opened
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md) and
  [R-547](547-the-pairs-budget-half-has-no-injection-row-of-its-own.md).
