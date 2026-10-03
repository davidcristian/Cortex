# The embedder's engine build is recorded nowhere

**Status:** done 2026-10-04
**Area:** memory
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

The brain logs the build of every generation server from the `system_fingerprint` on its streamed
chunks (ADR-0005 decision 9). The embedder is the one llama-server that line does not cover: a
`/v1/embeddings` reply on `b10680-d7bd3bfca` has only `data`, `model`, `object` and `usage`. Its
build is still `build_info` at `GET /props` on the embedder's endpoint and the image labels of the
memory overlay's `server` tag. The brain reads neither, and no reading names it yet.

The readings that need it already exist. `docs/readings/ranked-recall.md` compares recall across
dates: its 2026-09-24 deep model row says every MRR and `ABSENT` count equals the 2026-08-07
cortex row, and its 2026-09-28 row scores two candidates against that 2026-09-24 pick. Both later
runs embedded the corpus again through a fresh embedder started from the moving `server` tag, so a
build change between dates would change the pool every judge ranks, and no row names the
embedder's build.

**What remains.** The three live tests that embed through the embedder,
`test_rerank_judge_live.py`, `test_rerank_judge_wide_live.py` and `test_recall_floor_live.py`
under `brain/packages/inference/tests/`, read `GET /props` at `_EMBEDDER` before the first embed
through `served_build` in `tests/served_build.py` and print `embedder  <build_info> at <endpoint>`,
the way `_served` in `test_thinking_switch_live.py` prints the generation server's. The task
closes when one run shows that line against the real embedder and a row in `ranked-recall.md`
names the build it printed. The cheapest such run is `test_recall_floor_live.py`, which needs the
CPU embedder alone and no card. A `GET /props` from `LlamaCppEmbedder`
([embedder.py](../../../brain/packages/embedding/src/cortex_embedding/embedder.py)), logged the way
the generation line is, would not reach these readings: the tests build their own
`LlamaCppEmbedder`, and pytest shows no log record of a passing test, since the brain's pytest
settings set no `log_cli`. That line serves a running stack whose recall changed after a pull, and
no such change has been recorded.

## History

- 2026-09-24: Opened by the close of
  [R-622](622-only-one-endpoint-in-one-mode-records-its-engine-build.md), which records every
  generation server's build and found the embeddings reply names none.
- 2026-10-03: the consumer condition has been true since 2026-09-24, so the entry is now
  actionable. The 2026-09-24 deep model row of `docs/readings/ranked-recall.md`, committed three
  hours after this entry, compares its counts with the 2026-08-07 row, and the 2026-09-28 row
  compares two candidates with the 2026-09-24 pick; neither names the embedder's build, and the
  `judge_row.py` drivers of both runs (under `measurements/sitting2-2026-09-24/` and
  `measurements/sitting-2026-09-28/drivers/`) start the embedder from
  `ghcr.io/ggml-org/llama.cpp:server`, while the 2026-09-24 launcher logged the image id of the
  `server-cuda` tag alone. The remedy moved from the brain's embedder to the three live tests
  above, since a log line in `LlamaCppEmbedder` would not reach a reading those tests produce. Not
  built tonight: the card was in use and the print needs a live run to check.
- 2026-10-04: done. `served_build` reads `build_info` off `GET /props`, fails the run before it
  embeds when the body names no build, and is unit-tested against a scripted `/props`; the three
  tests call it and both measurement runbooks say so. One `test_recall_floor_live.py` run against
  the CPU embedder (`server` tag, `-ngl 0`) printed `embedder  b10680-d7bd3bfca`, and the
  relevance floor section of `docs/readings/ranked-recall.md` names that build beside numbers
  equal to its 2026-08-08 column to the printed precision. The local `server` tag reads `b10680`
  at revision `d7bd3bfca` on its image labels and was last tagged 2026-08-30, before both
  September rows, so both embedded on that build unless the tag moved and moved back.
