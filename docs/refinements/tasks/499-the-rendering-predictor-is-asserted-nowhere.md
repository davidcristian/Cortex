# The rendering that predicts a tier's constrained verdict is printed and never asserted

**Status:** landed 2026-08-30
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-29 by the decline of
[R-475](475-a-tier-can-be-asked-what-its-template-answers.md), which refused to ship the prediction
as a deployment's boot time probe and left it carried in prose.

`test_thinking_switch_live.py` asks each server `POST /apply-template` and prints both renderings
ahead of its four cells, and reads neither. The rule tying them together is written down twice in
[ADR-0005](../../adr/ADR-0005-llamacpp-engine.md), in the mechanism section for two picks and in the
lineup section for eleven, and it is correct on every row measured: a tier whose prompt answers "do
not think" with a thought **already closed** holds the switch under a `response_format`, and one
whose prompt leaves the thought open does not. Nothing checks that. A run against a tier that broke
the rule would print the rendering that contradicts its own cells, and a reader comparing four
numbers to a wall of prompt text is the least likely person in this repo to notice.

**Why it was left.** The prediction is not load bearing any more, which is the whole of the decline
above: `trace_tokens=0` closes the thought at the sampler on any tier whose engine reads the key, so
the shipped side calls no longer depend on what a template renders. What is left is a record that
could check itself and does not, and the cost of it going stale is a wrong sentence in a document
rather than a wrong request on a wire.

**What would close it.** An assertion in the probe rather than anything that runs in a deployment,
which is the line the decline drew. It needs the one thing the declined probe also needed and could
not have: a way to tell a closed thought from an open one, which on the two families here is
`</think>` and `<channel|>`. Inside an integration probe that is fine, because a file pointed at a
server by hand may know a pick's vocabulary where the port may not, and the probe already prints
both markers today. The honest shape is probably a reported comparison rather than a hard failure,
so a tier that breaks the rule is named and measured rather than turning the whole run red. Two
smaller things belong in the same pass: the rendering must be compared on the **tail** and not for
plain inequality, since the failing pick's two prompts differ at the front and are byte identical at
the end, and the ADR's mechanism section quotes only tails, which is where that trap was found.

## Trail

- 2026-08-29: opened by the decline of
  [R-475](475-a-tier-can-be-asked-what-its-template-answers.md), whose ADR-0005 template-probe
  addendum re-measured the predictor on two picks on opposite sides of the split and declined to
  ship it as a probe, leaving the reading itself unchecked by anything that runs.
- 2026-08-30: landed as `scripts/switchtail.py` and `scripts/switchsamples.py`, run by `just
  switch-tail` over a sample the probe now writes, per the ADR-0005 rendered-tail addendum. The
  assertion went into a covered module rather than into the integration-marked probe, on the
  precedent the envelope harness's control arm set the same morning: a rule asserted in a file no
  gate runs is ungated and unmutatable, and a tier that breaks this rule is news to publish rather
  than a reason to red the run that found it. The reading is on the **tail** after the ask, the two
  sides of the rule are held at their real strengths, and a cell drawn under five times or a
  control arm that never deliberated publishes nothing. Re-deriving found the entry's own premise
  half wrong in a way that made the case stronger: the probe printed the renderings' **lengths**
  and never the renderings, so the reading was not on the page for anybody to do by eye. Published
  live on two picks from opposite sides of the split, Qwen3.5-0.8B Q8_0 and gemma-4-E4B QAT q4_0 on
  `b10680-d7bd3bfca`, both agreeing. What it opened is
  [R-509](509-a-third-familys-closed-thought-reads-as-an-open-one.md), the two families the reader
  can spell, and [R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), the nine lineup
  rows that have still never been through it.
