# The spontaneous-pick nudge's live uptake

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Trigger:** A deployment that delegates unprompted and pays for the pile in the user's wall clock.

The measured trade-off line gives the cortex a
concrete wall-clock reason to spread independent subtasks across distinct roster models, and
whether it takes that reason unprompted is unmeasured. A subagent-tier proxy would not test it
(the spawn tool is cortex-only, and the small subagents do not respect prompt framing the way the
cortex does), so the probe needs a live cortex. **Corrected 2026-07-19: that is agent-runnable
here, and this entry said it was not.** It read "cannot be validated on the 8 GB dev GPU
(gemma-12B, the cortex tier, does not fit)";
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) had already run the real cortex on that card
at `-ngl 99 --ctx-size 4096 --parallel 1`, beside its vision projector, which is the heavier case.
The roster is CPU-placed by default, so it contends for no VRAM. The probe is a resident cortex at
4K with the roster up and a prose-only ask carrying independent subtasks, and it is listed as
actionable now in [index.md](../index.md); what stays host-side is the same question at the
production 16K context with more than one slot. The trigger is a live cortex still folding
cheap-model picks into instruction text or piling same-model batches for latency; the fix is
stronger nudging behind the same spec seam (a worked example, a sharper phrasing), never a schema
change.
**Observed 2026-08-04, and the entry stays open**
([ADR-0018 addendum](../../adr/ADR-0018-heterogeneous-subagents.md) of that date). The probe ran on
the 24 GB card at the **production 16K context** with a single slot, not the 4K proposed above,
cortex resident (9676 MiB of `nvidia-smi` total used against 1893 MiB idle) and both CPU roster
servers up, driving the real tool loop over the real builders' dispatcher with `spawn_subagents`
as the only advertised tool. It found three things and none of them is the yes or no this entry
expected. **The probe as specified cannot answer the question**, because a prose-only ask does
not produce a batch: 20 turns over four asks carrying three or four independent subtasks each
emitted **zero** spawn calls, and `subagent`, `delegat`, `spawn` and `farm` appear zero times in
the twelve full reasoning traces, so delegation was never declined, it was never raised. That is
also the right call on this deployment, where the CPU tiers run at 0.35 tok/s (the E4B default)
and about 1 tok/s (the Qwen alternate), so a delegated paragraph costs minutes the cortex spends
in seconds. **Invited to delegate in ordinary prose** (no tool name, no model name, no
parallelism language) it delegates every time and piles the whole batch on ONE entry every time:
16 turns, 16 delegations, 0 spreads, with exactly one of the 15 batches whose arguments were
recorded carrying a `model` key at all, and that one putting all three subtasks on `qwen` (the
sixteenth turn was abandoned while its batch ran, and the alternate's server served nothing
during it, so it too was a pile on the default). And **the nudge is only
advertised where it matters least:** `build_spawn_spec` publishes the knob and the spread
sentence only when `not tools_enabled and len(roster.entries) > 1`, while `build_subagent_tools`
makes subagents tools-enabled whenever any tool registry is configured, so every tools-enabled
deployment gets the pinned note instead (built both ways off the live roster to confirm). One
correction to the advertised sentence came out of the same run: an entry holds one backend per
placement *target*, and with `gpu_endpoint` falling back to `endpoint` both targets dial one
server, so a same-entry batch whose ask fits the VRAM headroom once overlaps two ways rather than
serializing (measured on `qwen`: two subtasks launched in the same millisecond, the third when
the first released; the default entry, whose ask never fits, was strictly serial at 258.4 s,
208.7 s and 330.2 s). It is folded in here rather than opened as its own entry because it is the
same sentence, the same seam and the same fix, and because it makes the prize for spreading
smaller rather than opening new work. **The trigger sharpens accordingly.** Piling is now
measured, so the old wording would read as fired, but nothing is being paid for it while
unprompted delegation does not happen at all. What would make it bite is a deployment where the
cortex reaches for delegation on its own and the batch's wall clock is the user's: a tool-less
multi-entry roster in real daily use, or roster entries far enough apart that piling is visibly
slower. The fix is unchanged, and the probe is now cheap to repeat
(`packages/orchestrator/tests/test_spawn_nudge_live.py`, bring-up in
[runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md) section 3c).
**The arithmetic that shared this premise was corrected on 2026-08-09; the advertised sentence
deliberately was not.** The bounded admission wait derived its 3600 s from the serialization
reading as though it were unconditional, one day after the run above measured the two-way
overlap, so `scheduler.py`, its test, the derivation in
[ADR-0012](../../adr/ADR-0012-resource-governance.md) and the entry in
[resource-governance.md](../index.md#resource-governance) now carry both placements and call the bound an
upper bound rather than an equality. That correction is arithmetic behind a shipped constant,
pinned by a test, and it needs no guess about wording. This entry's sentence is prose a model
reads, it understates the prize for spreading rather than overstating it, and one deployment's
behaviour still does not say which wording would be taken, so it stays as written while its
module doc and its spec comment now say the understatement is deliberate. One word of the
parenthetical above went stale with it: the default entry's ask was re-measured to 3.5 GiB the
same day, so it fits the headroom once and overlaps exactly as `qwen` did rather than staying
strictly serial.
**What stays as written, listed rather than left to be rediscovered.** The sweep that finished
the arithmetic correction hours later read every restatement of the serial premise in the tree
and left five standing on purpose. Four of them are this sentence and its escorts: the advertised
text in `spawn_spec.py`, the pinned note beside it, the assertions in
`packages/core/tests/test_spawn.py` that pin both strings, and the live probe's docstring in
`packages/orchestrator/tests/test_spawn_nudge_live.py`, all of which now describe the wording as
a deliberate understatement instead of asserting the premise as fact, so the strings themselves
are untouched and the decline is legible at each of them. The fifth is a class rather than a
site: the historical narratives of the 2026-07-16 landing (the [ADR-0010
addendum](../../adr/ADR-0010-subagents.md), the entry above, and the area rows in
[index.md](../index.md)) report what was measured and decided on the day, which is accurate as
history and would be falsified by being rewritten; each already sits next to the correction that
supersedes it. Correctly scoped statements of the mechanism, the ones that say *sharing one
backend* or *per placement target*, were never wrong and were not touched.

## Trail

- 2026-07-16: Opened behind the measured trade-off advertisement and the spontaneous-model-picks
  entry landing as one prose change, as the residual asking whether a live cortex takes the new
  wall-clock reason unprompted.
- 2026-07-19: The claim that no card available to the agent could run the probe was struck as
  false, ADR-0029 having already run the real cortex on the 8 GB card beside its vision
  projector, and the probe moved onto the actionable-now list. The index count for this area was
  corrected from 1 to 2 the same day, this residual having been named in the area doc from the
  day it opened but never counted; the arithmetic that dropped it is visible in the index's own
  narrative, where two entries closed on 2026-07-16 and one opened behind them, so the count
  should have moved 4 to 3 and then 3 to 2 rather than 4 to 2 and then 2 to 1. Every other area
  counts its fix-when-it-bites entries as open (repo gates counts three, memory counts its ANN
  index and recall observability, resource governance counts five), so this was a slip rather than
  a convention, and a count that does not move for a still-open deferral loses an open item the
  same way a count moved for a half-closed one does. This entry deliberately did not move when
  host-side work was extracted to [docs/host/](../../host/index.md) later that day, on the rule that
  an entry whose work is code stays with its area even when only the host's hardware can see the
  trigger, since moving it would split a design decision from the area it belongs to; the host
  index lists it only among the things a sitting on that hardware could also settle.
- 2026-08-04: The probe ran on the 24 GB card at the production 16K context with a single slot,
  and it answered neither yes nor no: a prose-only ask never delegates at all, an invited one
  delegated in all 16 turns and piled the whole batch on one entry in all 16, and the knob is
  advertised only to a tool-less multi-entry deployment. The run also corrected the advertised
  sentence's premise (one backend per placement target, both targets dialling one server) and
  sharpened the trigger, and it left a repeatable probe at
  `packages/orchestrator/tests/test_spawn_nudge_live.py`. The index recorded that third finding as
  the one no card was needed for and the one that reframed the entry, the deployment it is shown to
  exclusively being the one whose subagents can do nothing but the prose work the cortex prefers to
  keep. Running at 16K rather than the 4K the recipe proposed also retired the context size as the
  thing host hardware was owed: the index recorded that what stays host-side is real use over time
  and not a context size, and the host index struck its own claim that this hardware buys "real use
  at production context" as narrower than it had been, the context not being what was missing.
- 2026-08-09: The arithmetic twin of the same premise, the bounded admission wait's 3600 s, was
  corrected where a test pins it, while this entry's advertised sentence was deliberately left as
  written and the understatement recorded at each of its five surviving sites.
- 2026-08-09: A sweep over the backlog's triggers read this entry as having delivered its
  observation on 2026-08-04, leaving the fix, which is fix-when-it-bites, and an observation only
  the host's hardware can make. That sweep recorded its reading as agreeing with the actionable-now
  paragraph, which in fact still named this entry among the items it called open, and it was that
  paragraph rather than the sweep's own line that was corrected two days later.
- 2026-08-11: The index's actionable-now paragraph stopped naming this entry, recording that the
  observation that bucket owed ran 2026-08-04 and what is left is the fix, which is
  fix-when-it-bites, plus an observation only the host's hardware can make: real use over months
  rather than 36 scripted turns, listed at [docs/host/](../../host/index.md).
