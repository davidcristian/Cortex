# The spontaneous-pick nudge's live uptake

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Trigger:** A deployment that delegates unprompted and pays for the pile in the user's wall clock.
**Verified:** 2026-09-19

The trade-off sentence ([R-122](122-measured-tradeoff-advertisement.md)) gives the cortex a
wall-clock reason to spread independent subtasks across distinct roster models. Whether it acts on
that reason unprompted is what this entry watches. A subagent-tier stand-in would not answer it,
since `wiring.py` offers the spawn tool to the cortex and the deep tier and never to a subagent,
and the small subagents do not follow prompt framing the way the cortex does.

**Observed 2026-08-04** ([ADR-0018 decision 8](../../adr/ADR-0018-heterogeneous-subagents.md)) on
the 24 GB card at the production 16K context with a single slot, cortex resident (9676 MiB of
`nvidia-smi` total used against 1893 MiB idle) and both CPU roster servers up, driving the real
tool loop over the real builders' dispatcher with `spawn_subagents` as the only advertised tool.
Three findings, none of them a yes or a no:

- A prose-only ask does not produce a batch at all. 20 turns over four asks, each with three or
  four independent subtasks, emitted zero spawn calls, and `subagent`, `delegat`, `spawn` and
  `farm` appear zero times in the twelve full reasoning traces. Delegation was never declined; it
  was never raised. That is the right call on this deployment, where the CPU tiers ran at 0.35
  tok/s (the E4B default) and about 1 tok/s (the Qwen alternate), so a delegated paragraph costs
  minutes the cortex spends in seconds.
- Invited to delegate in ordinary prose, with no tool name, no model name and no parallelism
  language, it delegates every time and puts the whole batch on one entry every time: 16 turns, 16
  delegations, 0 spreads. Exactly one of the 15 batches whose arguments were recorded had a
  `model` key at all, and it put all three subtasks on `qwen`.
- The setting is advertised where it matters least. `build_spawn_spec` publishes the `model`
  property and the spread sentence only when `not tools_enabled and len(roster.entries) > 1`,
  while `build_subagent_tools` makes subagents tools-enabled whenever any tool registry is
  configured, so every tools-enabled deployment gets the fixed-roster note instead.

The same run corrected the advertised sentence's premise: an entry holds one backend per placement
target, and with `gpu_endpoint` falling back to `endpoint` both targets dial one server, so a
same-entry batch whose ask fits the VRAM headroom once overlaps two ways rather than running one
task after another. Measured on `qwen`: two subtasks launched in the same millisecond, the third
when the first released. The default entry, whose ask was then thought not to fit, ran strictly
serially at 258.4 s, 208.7 s and 330.2 s; its ask was re-measured to 3.5 GiB on 2026-08-09, so it
fits the headroom once and overlaps the same way.

The sentence a model reads was deliberately left as written, because it understates the benefit of
spreading rather than overstating it, and one deployment's behaviour does not say which wording
would be taken. Five places now describe that as a deliberate understatement rather than asserting
the serial premise as fact: `spawn_spec.py`'s advertised text and the fixed-roster note beside
it, the two assertions in `packages/core/tests/test_spawn.py`, and the live probe's docstring in
`packages/orchestrator/tests/test_spawn_nudge_live.py`. Bring-up for the probe is
[runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md) section 3c.

The fix, when the trigger fires, is stronger prompting behind the same spec port (a worked
example, a sharper phrasing), never a schema change.

## History

- 2026-07-16: Opened behind the measured trade-off advertisement and the spontaneous-model-picks
  entry shipping as one prose change.
- 2026-07-19: The claim that no card available to the agent could run the probe was struck as
  false, ADR-0029 having already run the real cortex on the 8 GB card beside its vision projector.
  The index count for this area was corrected from 1 to 2 the same day, this entry having been
  named from the day it opened but never counted. It stayed with its area when host-side work was
  moved to [docs/host/](../../host/index.md), on the rule that an entry whose work is code stays
  with its area even when only the host's hardware can see the trigger.
- 2026-08-04: The probe ran, with the three findings above, and sharpened the trigger. Running at
  16K rather than the 4K the recipe proposed also retired the context size as something host
  hardware was owed: what stays host-side is real use over time.
- 2026-08-09: The arithmetic twin of the same premise, the bounded admission wait's 3600 s, was
  corrected where a test asserts it, so `scheduler.py`, its test,
  [ADR-0012](../../adr/ADR-0012-resource-governance.md) and
  [resource-governance.md](../index.md#resource-governance) now describe both placements and call
  the bound an upper bound rather than an equality.
- 2026-08-09: A review over the backlog's triggers read this entry as having delivered its
  observation on 2026-08-04, leaving the fix and an observation only the host's hardware can make.
- 2026-08-11: The index's actionable-now paragraph stopped naming this entry, recording that what
  is left is the fix plus an observation only the host's hardware can make: real use over months
  rather than 36 scripted turns.
- 2026-09-11: Every claim the tree can answer was read against it and held. The admission wait was
  raised to 7200 s on 2026-08-25, three run deadlines, so it outlasts both attempts one admission
  can hold; the sentence a model reads is unchanged. Nothing recorded since 2026-08-04 reports an
  unprompted delegation.
- 2026-09-13: The code half was re-read and is unchanged, and the entry took the verified date the
  reading two days earlier had withheld. That date says the entry's claim was held against the
  code, and says nothing about the trigger.
- 2026-09-19: The code half holds. What moved is the rate the 2026-08-04 finding argues from: the
  0.35 and about 1 tok/s were read on the unpinned CPU tier, and fixing the thread count raised
  the published per-slot rates from 0.18 to 1.35 tok/s to 3.0 to 12.4
  ([ADR-0004](../../adr/ADR-0004-model-lineup.md)). A subtask decoded to the shipped token cap
  still takes over a minute, so declining to delegate is still the cheaper call. The same record
  measured what a pile costs on one server: two attempts decoding at once each took about 1.4
  times as long as one alone. Whether spreading onto a second entry avoids that depends on the two
  servers not sharing cores, which nothing has measured. The trigger has not fired.
