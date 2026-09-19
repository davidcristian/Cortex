# The shipped reasoning-off pair contains a flag that cancels the other

**Status:** declined 2026-09-02
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

Every subagent server this repo starts uses both `--chat-template-kwargs
'{"enable_thinking": false}'` and `--reasoning-budget 0`, and `scripts/flagcheck.py` derives the set
of those servers from the stack's own wiring and requires the pair on each. Measured on the shipped
subagent pick over two llama.cpp builds, the budget alone wrote no reasoning character on 30 draws
of the exact request a delegated run sends, and the pair wrote a trace on 10 of 30, opened with a
garbled channel marker on 5, and returned an empty reply cut at the cap on 8. The pair and the kwarg
alone were identical on 20 of 20 matched seeds. So the second flag is not redundant with the first,
as the compose comment said: it turns the first off.

Dropping the kwarg is three decisions and not one. It is the flag the Qwen half of the roster's
template reads, and no Qwen entry writes to that channel at all, so a change made for the gemma pick
has to say what it does to the other family; `scripts/flagcheck.py` requires the pair on every
subagent server, so the check has to express "this flag, on this family" before the tree can make
the change; and the E4B pick's measured injection resistance was taken with thinking off.

## History

- 2026-08-30: opened by the close of
  [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), whose ADR-0049 attributed the
  garbled channel marker to the kwarg and measured the budget alone stopping the trace outright on
  two builds.
- 2026-09-02: declined, by ADR-0049, which took the cheap first step and found the premise wrong
  about what it measured. The budget alone was re-drawn seed-paired at 40 draws over all four report
  bodies on the GPU and again on the CPU image the override ships: it wrote no reasoning character
  and lost 11 of 40 answers to the reply itself, 9 arriving as a narration or a plan and 2 as a
  thinking process written into `reply` and cut at the cap, where the pair lost 3 of 40 to the
  channel; on the plain request shape it wrote the thinking process as the reply on 33 of 40; and on
  the Qwen pick it deliberated to the cap on 40 of 40 across both shapes, that template opening the
  thought inside the prompt where the sampler sees no start. So the second flag cancels the first
  and the first alone is worse, on both families. The pair stays on every subagent server,
  `scripts/flagcheck.py` is unchanged, and the roster question does not arise. The deprecation's
  successor `--reasoning off` matched the pair character for character on 40 of 40 seeds, which is
  recorded on [R-461](461-the-tiers-thinking-flag-is-deprecated.md). Opened
  [R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md) and
  [R-526](526-the-pairs-budget-half-is-inert-beside-the-kwarg.md).
