# The shipped reasoning-off pair contains a flag that disarms the other

**Status:** declined 2026-09-02
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-30 by the close of
[R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), whose attribution found a repair
this repo cannot take in one edit.

Every subagent server this repo starts carries both `--chat-template-kwargs
'{"enable_thinking": false}'` and `--reasoning-budget 0`, and `scripts/flagcheck.py` derives the set
of those servers from the stack's own wiring and requires the pair on each. Measured on the shipped
subagent pick over two llama.cpp builds, the budget alone wrote **no reasoning character on 30
draws** of the exact request a delegated run sends, and the pair wrote a trace on 10 of 30, opened
with a garbled channel marker on 5, and returned an empty reply cut at the cap on 8. The pair and
the kwarg alone were identical on 20 of 20 matched seeds. So the second flag is not redundant with
the first, as the compose comment says: it turns the first off.

**Why it was left.** Dropping the kwarg from this tier is three decisions and not one. It is the
flag the **Qwen** half of the roster's template reads, and the lineup's own reading is that no Qwen
entry writes to that channel at all, so a change made for the gemma pick has to say what it does to
the other family. `scripts/flagcheck.py` holds every subagent server to the pair, so the gate has to
carry "this flag, on this family" before the tree can express the change at all, and a gate with a
per family rule needs the family to be something it can read rather than a name in a table.
And the E4B pick's measured injection robustness was taken with thinking off, so the arm that says
the pick is still safe without the kwarg does not exist yet.

**What would close it.** The order matters, and the first step is the cheap one. Re-measure the
**budget alone** arm at the size the pair was measured at, over all four report bodies rather than
the two that leak, and on the CPU image the subagents override actually ships, since every draw
behind this entry is GPU. If it holds, the decision is a roster shaped one: whether the kwarg is a
per entry flag rather than a tier wide one, which is the shape
[R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md) is already circling, and whether
`flagcheck.py` derives the required flags from the entry's family the way it already derives the set
of servers from the wiring. The injection arm is the last step and not the first: it is only owed if
the kwarg is actually going away.

## Trail

- 2026-08-30: opened by the close of
  [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), whose ADR-0005 marker addendum
  attributed the garbled channel marker to the kwarg and measured the budget alone stopping the
  trace outright on two builds.
- 2026-09-02: **declined**, by the ADR-0005 budget-alone addendum, which took the cheap first step
  and found the premise wrong about what it measured. The budget alone was re-drawn seed-paired at
  40 draws over all four report bodies on the GPU and again on the CPU image the override ships:
  it wrote no reasoning character and lost 11 of 40 answers to the reply itself, 9 arriving as a
  narration or a plan and 2 as a thinking process written into `reply` and cut at the cap, where
  the pair lost 3 of 40 to the channel; on the plain request shape it wrote the thinking process as
  the reply on 33 of 40; and on the Qwen pick it deliberated to the cap on 40 of 40 across both
  shapes, that template opening the thought inside the prompt where the sampler sees no start. So
  the second flag disarms the first and the first alone is worse, on both families. The pair stays
  on every subagent server, `scripts/flagcheck.py` is unchanged, and the roster question does not
  arise. The deprecation's successor `--reasoning off` matched the pair to the character on 40 of
  40 seeds, which is recorded on
  [R-461](461-the-tiers-thinking-flag-is-deprecated.md). Opened
  [R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md) and
  [R-526](526-the-pairs-budget-half-is-inert-beside-the-kwarg.md).
