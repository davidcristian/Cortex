# The rendering that predicts a tier's constrained result is printed and never asserted

**Status:** done 2026-08-30
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

`test_thinking_switch_live.py` asks each server `POST /apply-template` and prints both renderings
ahead of its four cells, and reads neither. The rule connecting them is written down twice in
[ADR-0005](../../adr/ADR-0005-llamacpp-engine.md), in the mechanism section for two picks and in the
lineup section for eleven, and it is correct on every row measured: a tier whose prompt renders "do
not think" with a thought already closed honours the switch under a `response_format`, and one whose
prompt leaves the thought open does not. Nothing checks that. A run against a tier that broke the
rule would print the rendering that contradicts its own cells.

The prediction no longer decides any shipped behaviour, since `trace_tokens=0` closes the thought at
the sampler on any tier whose engine reads the key. What is left is a record that could check itself
and does not, and the cost of it going stale is a wrong sentence in a document rather than a wrong
request on a wire.

## History

- 2026-08-29: opened by the decline of
  [R-475](475-a-tier-can-be-asked-what-its-template-answers.md), which re-measured the prediction on
  two picks on opposite sides of the split and declined to ship it as a deployment's boot-time
  probe.
- 2026-08-30: closed as `scripts/switchtail.py` and `scripts/switchsamples.py`, run by `just
  switch-tail` over a sample the probe now writes, per ADR-0050. The assertion went into a covered
  module rather than into the integration-marked probe, on the precedent the envelope harness's
  control set the same morning: a rule asserted in a file no check runs is unchecked and cannot be
  mutation tested, and a tier that breaks this rule is news to publish rather than a reason to fail
  the run that found it. The reading is on the tail after the request, the two sides of the rule are
  compared at their real strengths, and a cell drawn under five times or a control that never
  deliberated publishes nothing. Checking the premise found it half wrong in a way that made the
  case stronger: the probe printed the renderings' lengths and never the renderings, so the reading
  was not on the page for anybody to do by eye. Published live on two picks from opposite sides of
  the split, Qwen3.5-0.8B Q8_0 and gemma-4-E4B QAT q4_0 on `b10680-d7bd3bfca`, both agreeing. Opened
  by it: [R-509](509-a-third-familys-closed-thought-reads-as-an-open-one.md), the two families the
  reader can recognise, and [R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), the
  nine lineup rows that have never been through it.
