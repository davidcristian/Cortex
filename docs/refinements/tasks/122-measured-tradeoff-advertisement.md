# Measured trade-off advertisement

**Status:** done 2026-07-16
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

Roster descriptions are config-authored text (`description` per entry,
`CORTEX_SUBAGENTS_MODEL_DESCRIPTION` for the default). Deriving them from measured latency or
robustness numbers stays declined: those strings are deployment-specific, and safety does not
depend on them, so wrong text misleads only the optimization.

**Shipped 2026-07-16** ([ADR-0018 decision 8](../../adr/ADR-0018-heterogeneous-subagents.md)) as
the structural half, which the spec asserts independently of config. `spawn.py`'s description had
told the cortex that subagents "run concurrently" and that delegation was "worth parallelizing".
The measured reality (ADR-0012 decision 9, live on the Qwen-2B CPU override: two same-model
spawns 10.0 s against two across two backends 4.8 s, a ratio of 2.08) is that each roster entry
holds one backend whose `SingleResidentModelManager` lease is held for the whole stream, so
same-model subtasks run one after another and only distinct-model subtasks overlap. The mechanism
is an `asyncio.Lock` per entry, held for the stream, confirmed in `model.py`.

The base description dropped the blanket claim, the choice note points the cortex at spreading
work across distinct models as the wall-clock win, and the note about a fixed or single-entry
roster says a batch groups independent work rather than speeding it up.

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area, among the
  Slice 8.6 heterogeneous-roster deferrals recorded at ADR-0018.
- 2026-07-16: Shipped as the structural half, the deriving-strings-from-numbers half staying
  declined. The same prose change delivers the spontaneous-model-picks hint
  ([R-123](123-spontaneous-model-picks.md)), and what it left open is that hint's live uptake
  ([R-124](124-nudge-live-uptake.md)).
- 2026-08-04: The live probe measured a correction to the sentence this entry shipped: an entry
  holds one backend per placement target, and with `gpu_endpoint` falling back to `endpoint` both
  targets dial one server, so a same-entry batch whose ask fits the VRAM headroom once overlaps
  rather than running one task after another. That run read the shipped sentence as conservative
  on the deployment it measured rather than as wrong, so the correction went into the nudge entry.
- 2026-08-09: The advertised sentence was deliberately left as written, its understatement
  recorded at `spawn_spec.py`, its module doc, the assertions in
  `packages/core/tests/test_spawn.py` and the live probe's docstring, while the arithmetic that
  had shared the serial premise was corrected where a test asserts it.
