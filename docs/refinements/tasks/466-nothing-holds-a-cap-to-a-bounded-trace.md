# Nothing holds a cap sized on the answer to a tier whose trace is bounded

**Status:** declined 2026-09-12
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-27 by the close of
[R-458](458-the-ports-thinking-switch-is-conditional.md), which made the failure visible at runtime
and left it possible to write.

The pairing rule this repo keeps is that a `max_tokens` sized on the wanted answer is only safe
against a **bounded trace**, because a reasoning model spends its budget thinking first. Three
shipped bounds pair a cap with `thinking=False` and took that as the bound: `RECAP_BOUNDS`,
`TITLE_BOUNDS` and `rank_bounds(k)`. Measured, that switch is a request the deployment may not
honour, so the rule's precondition can be false at runtime while every gate is green, and the fourth
caller to write such a pair will write it exactly the same way.

What exists at runtime is the report, not the hold: `drain_text` logs the model and the characters it
dropped when a request that asked for no thinking is answered with a trace, and
`test_thinking_switch_live.py` answers the question per shape for a deployment that thinks to ask.
Both are after the fact.

**What the request now carries.** Two days after this was opened, all three of those bounds gained
`trace_tokens=0` beside the switch (ADR-0005 request-lever addendum). That number is not another
request to a chat template: llama.cpp reads it off the body as a sampler, so where the engine reads
the key the trace is bounded by the request itself, on the schema-carrying shape the switch was
measured losing as well. Measured at a hundred draws a cell on the shipped subagent pick, on each of
the two builds this host can start, the switch alone left 85 and 86 draws of 100 deliberating into an
empty capped reply and the switch with the zero left 0 of 100. Whether a given engine reads the key is asked once at boot
(`CORTEX_INFERENCE_TRACE_LEVER`), logged, and asked again by hand from the GPU runbook. So the
precondition the rule needs is now a value the caller sends rather than one the deployment's argv
decides, on every shipped pair, and what remains unbounded at runtime is a deployment whose engine
does not read the key.

**Why a hold was not built.** A gate would need a fact the core is built not to carry. Whether a
tier's trace is bounded by its argv (`--reasoning-budget`) lives in the model host's config and in
two compose files, and the core reaches inference through a port that deliberately says nothing
about how the server was started. Giving the port a "the trace is bounded here" capability is the
obvious move and the wrong one on today's evidence: llama.cpp offers no way to ask, so the value
would be a deployment's own claim about itself, which is a setting that can be wrong in the other
direction. The subagent attempt is the case that settles it: it pairs a cap with no switch at all and
rests on the two flags every subagent server is started with, so a rule that read only the request
would reject the one caller whose bound is real.

**Why the other two candidates are declined.** A `crosscheck` entry tying each shipped bound to its
tier's own budget flag would hold the wrong value twice over. The cortex tier ships
`CORTEX_REASONING_BUDGET` at llama.cpp's own word for unbounded, and that default is deliberate:
the same tier serves a user's reply, whose trace is the thinking status the overlay renders
(ADR-0020), so a deployment default that bounded it would blank a surface a person is reading to pay
for a side call the request already bounds. That is also what refutes the third candidate, the
accepting answer that the repair is a documented non-negative budget on every tier a bound caller
uses: the tier a bound caller runs on is the tier the reply runs on, and the two want opposite
answers. The per-request count is the value that separates them, and it landed.

## Trail

- 2026-08-27: opened by the close of
  [R-458](458-the-ports-thinking-switch-is-conditional.md), which made the unhonoured switch visible
  at runtime through `drain_text` and left the pairing writable.
- 2026-09-12: **declined**, and the body is corrected twice. It said four shipped bounds pair a cap
  with the switch; there were three on the day it was written and there are three now
  (`RECAP_BOUNDS`, `TITLE_BOUNDS`, `rank_bounds(k)`), the fourth cap in the tree being
  `SubagentAttempt`'s, which names no switch and rests on its tier's flags by decision. And the
  premise moved under it: every one of the three has carried `trace_tokens=0` since 2026-08-29, which
  is a sampler the engine applies rather than a request a template may ignore, so on a deployment
  whose engine reads the key the rule's precondition is true by construction. The three candidates
  this entry left are all declined above, the first on the argument it was opened with and the other
  two because the value they would hold is the cortex tier's budget default, which is unbounded on
  purpose for the reply that shares that tier. What survives is narrower and is a fact about how a
  call is written rather than about how a server was started: nothing holds a fourth side call to the
  zero the three carry, which is
  [R-650](650-nothing-holds-a-side-call-to-the-request-level-zero.md).
