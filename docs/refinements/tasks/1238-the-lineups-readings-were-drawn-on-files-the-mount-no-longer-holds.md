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
- the injection rows of each tier, of which gemma-4-31B's is still owed;
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
- 2026-11-28: the leading-system-message rows and the two live image tests are drawn on the files
  the tier defaults name, on build b12375, which closes both lines. Every template took the shape
  written before the draw: gemma renders each system message in a turn of its own, Qwen3.8 merges
  them, and every Qwen3.5 and Qwen3.6 file merges two and drops a third, so no file raises now;
  ADR-0071's context, ADR-0004 decision 6 and the CPU subagent runbook now say so
  ([system message templates](../../readings/system-message-templates.md)). The attached-picture
  turns read every word at 993 and 2883 prompt tokens, as before. The engine's own budget for a 4K
  screen rose from 266 to 482 tokens. Without `--ubatch-size` the engine now cuts budget 1024 to
  the 512 micro-batch rather than aborting, so the micro-batch test asserts that cut
  ([vision capture](../../readings/vision-capture.md#image-tokens-and-the-budget)).
  Still owed: the injection rows and reply envelopes on the earlier files, the CPU subagent
  server's memory, the deep tier's cost, the drafter's cost and rate, and gemma-4-31B's switched
  tails.
- 2026-11-28: the injection text rows still on the earlier files are drawn on the files the mount
  holds, which closes their part of the injection line: the cortex pick, gemma-4-E4B and
  gemma-4-E2B on the card at b12375, and all five subagent entries on the CPU at b10680, the
  Qwen3.5-4B over seven repetitions. Every cell reads the same as its earlier one by a two-sided
  Fisher test at 0.05 ([current files](../../readings/injection-rows-current-files.md)). The
  reply envelope line is closed: the pick delivers 110 of 128 against 117 (p 0.24), the 2B's row
  of 2026-11-24 reads 85 against 97 (p 0.13), and gemma-4-E2B, Qwen3.5-0.8B and Qwen3.5-4B have
  their first rows under the shipped wording
  ([reply envelope](../../readings/reply-envelope.md#the-current-files)). Still owed on the
  injection line: gemma-4-31B, whose file does not fit beside the user's apps at the deep tier's
  argv.
- 2026-11-28: the memory lines are closed. The CPU subagent server, started as its compose
  service starts it under 8g, read 6,940 MiB in its cgroup loaded and 7,136 MiB with both slots
  filled, 0.87 of the cap, with 3,029 MiB of anonymous memory and no oom event, so the 3.0 GiB
  memory request stays and the quotes of about 2.5 GiB now give 3,029 MiB
  ([subagent budget](../../readings/subagent-budget.md#the-cpu-server-as-compose-starts-it)).
  The deep tier's cost needed no draw: the pick's file is the one measured, with rows on b12375
  at 16384 and `q8_0` from 2026-11-21 and 2026-11-23, and gemma-4-31B's file and drafter have
  rows from 2026-11-20 ([deep tier](../../readings/kv-cache-deep-whole.md#the-rows)). The
  model-swap runbook and ADR-0004 now give those, 18,355 to 18,384 MiB plain and 707 MiB for the
  drafter at `q8_0`, in place of the earlier file's 19125 to 20783 and the `F16` drafter's
  1000 MiB. Still owed: gemma-4-31B's switched tails and injection rows, and the deep drafter's
  rate, which waits on a rate row.
