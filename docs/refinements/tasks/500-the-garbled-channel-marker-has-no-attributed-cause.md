# The garbled channel marker that eats a delegated answer has no attributed cause

**Status:** landed 2026-08-30
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-29 by the close of
[R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md), whose measurement produced a
contrast it could explain but not attribute.

On a server carrying both shipped reasoning-off flags, 13 draws in 76 of the request a delegated run
really sends wrote 1582 to 4078 characters into the reasoning channel, and **11 of the 13 open with a
fragment of a channel marker**, the literal `</channels>`, `t</channell>`, `</chaann>`, `h</cha>`,
`h</c>` or a bare `>`, after which the answer itself is written into the channel in plain prose and
the run comes back cut at the cap with an empty `reply`. On an unflagged twin of that server the same
prompt deliberated on 8 draws of 8 and produced no such fragment on any of them: every trace there
opens as ordinary deliberation.

The reading the addendum ships is that the forced close a budget of zero performs, which the
request-lever addendum already measured landing **after** a thought's start sequence and leaking the
word `thought` into one reply in 58, is being emitted where no thought was open, mangled, and then
read by the server's own parser as a channel switch. It explains all four readings and it is an
explanation. Nothing here read the handler that writes those markers, and one build was measured.

**Why it was left.** The consequence is already recorded where an operator meets it, in the compose
command block, [ADR-0010](../../adr/ADR-0010-subagents.md) and
[docs/runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md), and the repair is a lineup
decision rather than an engine one: no Qwen entry of the row writes to that channel at all across 864
draws (ADR-0028 row addendum). Attributing the marker changes none of that. What it would buy is the
ability to say whether a build that fixed it had fixed it, which today would be read off a rate on
one prompt over one pick.

**What would close it.** Two halves, and the first is worth more than the second.

The **probe** half is the one [R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md) asked
for and this close did not deliver. The key arm above was drawn by hand off `build_payload`, because
`brain/packages/orchestrator/tests/test_envelope_cost_live.py` runs the shipped `SubagentRunner` and
therefore sends exactly what `PlacedAttempt` sends, which names no count. A knob on that harness that
substitutes `trace_tokens` into the bounds on the way past, the way `_Recording.substitute` already
does for the schema, would make every cell of that addendum reproducible by a committed file. It
would also want a reading of the fragment itself rather than of the trace's length, since a trace
that opens with a marker fragment and one that opens with a plan are two different findings that the
`reasoning_chars` column cannot tell apart.
`brain/packages/inference/tests/test_thinking_switch_live.py` is **not** the home for it: its control
asserts that the no-switch arm deliberated, which a correctly flagged server will not do.

The **attribution** half is a reading of llama.cpp's gemma-4 chat handler, specifically what it emits
and what it expects when a reasoning budget of zero forces a thought closed under a grammar built
from a `response_format`. That is a source reading rather than a measurement, and the cheap
approximation is a second build: the same request on an older and a newer image, with the rate and
the fragment shapes compared, which is the same instrument the request-lever addendum used to decide
that the engine range checks its own key.

## Trail

- 2026-08-29: opened by the close of
  [R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md), whose ADR-0005 firm-prompt
  addendum measured the contrast between a flagged server and its unflagged twin, ships the forced
  close as the best explanation of it, and labels that explanation as one.
- 2026-08-29: [R-495](495-the-forced-thought-can-leak-its-own-start-tag.md) records the seam this
  entry's explanation is drawn from, the same forced close delivering a start tag as a whole valid
  answer. Its committed probe already prints a leak count, so the reading of the fragment this
  entry asks for and the rate that entry asks for are one instrument.
- 2026-08-30: **landed** by the ADR-0005 marker addendum, which split the shipped pair into its two
  flags and attributed the marker to one of them. `POST /apply-template` on both builds says the two
  flags are not one lever: the kwarg drops the `<|think|>` the template injects and the budget leaves
  the prompt byte identical to an unflagged server's. Split into single flag arms, `--reasoning-budget
  0` alone wrote no reasoning character on 30 draws over two builds, while the kwarg alone reproduced
  the trace, the fragments and the empty reply and was **identical to the shipped pair on 20 of 20
  matched seeds**, so on the pair the budget is inert. The fragments are this template's own closing
  marker `<channel|>` written with a slash in it. That excludes the forced close, which this entry's
  explanation rested on, since the kwarg alone arm sets no budget anywhere; it excludes the build,
  the same interaction appearing on the build the origin measured; and it excludes the cap by
  position, the fragment being at character zero of the trace. What it leaves is the parser step,
  why an unmatched close carries the whole answer into the channel, which is inference from the
  marker's shape and is recorded in that addendum rather than as its own entry, no repair depending
  on it. The two halves this close opens are the repair,
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), and the probe half this
  entry asked for and this close also drew by hand,
  [R-512](512-no-committed-probe-splits-the-reasoning-off-pair.md).
