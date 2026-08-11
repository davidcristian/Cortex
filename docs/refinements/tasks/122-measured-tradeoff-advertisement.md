# Measured trade-off advertisement

**Status:** landed 2026-07-16
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

Roster descriptions are config-authored text
(`description` per entry, `CORTEX_SUBAGENTS_MODEL_DESCRIPTION` for the default); deriving or
cross-checking them from measured latency/robustness numbers is a later refinement behind the
same spec-building seam. Wrong text misleads only the optimization. Safety is deterministic.
**Landed 2026-07-16: the advertisement now states the measured trade-off, not a blanket
parallel claim** ([ADR-0018 addendum](../../adr/ADR-0018-heterogeneous-subagents.md)). The entry
read the "measurement" as *deriving the config description strings from numbers*; that half is
still declined and stays config-authored, because those strings are deployment-specific and
safety is deterministic regardless. What was measurable and worth advertising was the
*structural* trade-off the spec asserted independently of config: `spawn.py`'s description told
the cortex subagents "run concurrently" and delegation was "worth parallelizing", a blanket
parallel claim. The measured reality (ADR-0012 admission-wall addendum, live on the Qwen-2B CPU
override: two same-model spawns 10.0 s vs two across two backends 4.8 s, ratio 2.08) is that
each roster entry holds one backend whose `SingleResidentModelManager` lease is held for the
whole stream, so same-model subtasks serialize and only distinct-model subtasks overlap. The
base description dropped the blanket claim, the choice note now points the cortex at
distinct-model spread as the wall-clock lever, and the pinned/single-entry note says a batch
groups independent work rather than speeding it up. Measurement reused from the same-day
admission-wall work, cited as prior; the mechanism (`asyncio.Lock` per entry, held for the
stream) is confirmed in `model.py`.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc, kept
  verbatim, among the Slice 8.6 heterogeneous-roster deferrals recorded at ADR-0018.
- 2026-07-16: Landed as the structural half, the deriving-strings-from-numbers half staying
  declined and config-authored; the same prose change carries the spontaneous-model-picks nudge,
  and the residual it left is the nudge's live uptake.
- 2026-08-04: The live probe of that residual measured a correction to the sentence this entry
  landed: an entry holds one backend per placement *target*, and with `gpu_endpoint` falling back
  to `endpoint` both targets dial one server, so a same-entry batch whose ask fits the VRAM
  headroom once overlaps rather than serializing. The sentence at issue is the shipped line telling
  the cortex that subtasks sharing one model run one after another, which that run read as
  conservative on the deployment it measured rather than as wrong, so the correction was folded into
  the nudge entry rather than opened as work of its own.
- 2026-08-09: The advertised sentence was deliberately left as written, its understatement
  recorded as such at `spawn_spec.py`, its module doc, the assertions in
  `packages/core/tests/test_spawn.py` and the live probe's docstring, while the arithmetic that
  had shared the serial premise was corrected where a test pins it.
