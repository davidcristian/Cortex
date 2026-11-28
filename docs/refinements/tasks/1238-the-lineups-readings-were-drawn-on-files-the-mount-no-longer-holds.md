# The lineup's readings were drawn on files the mount no longer holds

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-28

The models mount was rebuilt on 2026-11-15 and 2026-11-16, and every tier default now names a file
no reading was drawn on. What a walk over the GGUF headers on the mount showed on 2026-11-16:

- **gemma-4** (12B, E4B, E2B, 26B-A4B, 31B): the `google/gemma-4-<size>-it-qat-q4_0-gguf` files are
  gone. Each tier names `unsloth/gemma-4-<size>-it-qat-GGUF/gemma-4-<size>-it-qat-UD-Q4_K_XL.gguf`,
  whose weight tensors are `Q4_0` (`general.file_type` 2) and whose other tensors are `F32`.
- **Both gemma chat templates changed.** By the first eight hex digits of the template's SHA-256,
  the dense entries moved from `ae53464b` to `845f1ee4` and the E entries from `0a2c8073` to
  `241c50d8` ([template effort settings](../../readings/template-effort-settings.md)).
- **Qwen3.5** (0.8B, 2B, 4B, 9B) and **Qwen3.6-35B-A3B** are builds under `-MTP-GGUF` directories
  with `nextn_predict_layers` 1 in the header. The 2B is 1,329,851,808 bytes against the 1.19 GB
  measured. The 0.8B and the 2B have template `ea210e5b`, which no reading records. The 9B is
  `Q4_K_M`, and its rows were drawn on `UD-Q4_K_XL`.
- **The cortex projector** is `mmproj-F32.gguf`, 209,522,240 bytes, with an audio encoder beside
  the vision one. **The deep drafter** is `mtp-gemma-4-31B-it-Q8_0.gguf`, 514,705,920 bytes, and
  the drafter readings were drawn on an `F16` file of 954,843,360 bytes.
- The same as measured: `Qwen3.8-27B-UD-Q4_K_M` (template `12827f24`) and the embedder.

What would close it, the picks first and the other candidates after:

- the lineup's switched tails (`just switch-lineup`) and the leading-system-message rows, since
  both read the template;
- the injection rows of each tier and the reply envelope of the subagent entries;
- the cortex's VRAM figure behind `CORTEX_VRAM_CORTEX_GB` and the CPU subagent server's memory
  reading under its 8 GiB cap;
- the deep tier's cost, and the drafter's cost and rate, behind `CORTEX_SWAP_BRAIN_VRAM_MIB`;
- the two live image tests, which name the new projector.

A row that reads the same closes its line here, and one that differs changes the record citing it.

## History

- 2026-11-16: filed when the tier defaults, the lineup harness and the live tests were repointed at
  the files the mount holds. No model was loaded that day, so no row was redrawn.
- 2026-11-20: ADR-0004 decision 8 now names `Qwen3.8-27B-UD-Q4_K_M` as the deep pick, the one
  lineup file whose rows were drawn on the file the mount holds. The deep tier's cost and the
  drafter's cost and rate above are gemma-4-31B's, the alternate's, and come after the picks.
- 2026-11-24: the injection text rows of the four Qwen3.5 entries and the reply envelope of the
  2B were drawn on the files the mount holds, at the engine's sampler on build b12375, as the
  engine's cells of [card samplers](../../readings/card-samplers.md). The 2B read 14 framed obeyed
  of 100 and the 9B 2, where the [injection text rows](../../readings/injection-text-rows.md) table
  has 8 and 7 on the earlier files and build; that table is not changed yet.
- 2026-11-27: the mount holds the files this task names, at the byte sizes above. The
  [injection text rows](../../readings/injection-text-rows.md) table now gives each Qwen3.5
  entry's card counts of 2026-11-24 beside its earlier ones, which closes that line for their card
  cells; the CPU cells and the other entries are still on the earlier files. The cortex's VRAM
  figure is satisfied: `CORTEX_VRAM_CORTEX_GB` rests on the 8,868 MiB peak of the default file
  with `mmproj-F32.gguf` and its drafter in [tier drafters](../../readings/tier-drafters.md). The
  deep drafter's rate waits on a rate row, since the card's power limit read 175, not the
  baseline's 155. The other card rows did not fit this slot.
- 2026-11-28: the switched tails line is closed for ten entries by R-529's draw on build b12375:
  gemma-4 12B, E4B, E2B and 26B-A4B, Qwen3.5 0.8B, 2B, 4B and 9B, Qwen3.6-35B-A3B and Qwen3.8-27B
  each rendered both prompts byte for byte as the earlier files did on b11913 and repeated its four
  counts, the new gemma templates included
  ([thinking switch](../../readings/thinking-switch.md#the-lineups-switched-tails)). It stays open
  for gemma-4-31B, whose file does not fit the card whole at the recipe's argv
  ([R-1383](1383-the-lineup-recipe-serves-gemma-4-31b-whole-and-the-card-cannot-hold-it.md)). The
  leading-system-message rows are still owed.
