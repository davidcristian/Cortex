# The embedder's engine build is recorded nowhere

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-10-03

The brain logs the build of every generation server from the `system_fingerprint` on its streamed
chunks (ADR-0005 decision 9). The embedder is the one llama-server that line does not cover: a
`/v1/embeddings` reply on `b10680-d7bd3bfca` has only `data`, `model`, `object` and `usage`. Its
build is still `build_info` at `GET /props` on the embedder's endpoint and the image labels of the
memory overlay's `server` tag, and nothing in the brain or its live tests reads either.

The readings that need it already exist. `docs/readings/ranked-recall.md` compares recall across
dates: its 2026-09-24 deep model row says every MRR and `ABSENT` count equals the 2026-08-07
cortex row, and its 2026-09-28 row scores two candidates against that 2026-09-24 pick. Both later
runs embedded the corpus again through a fresh embedder started from the moving `server` tag, so a
build change between dates would change the pool every judge ranks, and no row names the
embedder's build.

**What would close it.** The three live tests that embed through the embedder,
`test_rerank_judge_live.py`, `test_rerank_judge_wide_live.py` and `test_recall_floor_live.py`
under `brain/packages/inference/tests/`, read `GET /props` at `_EMBEDDER` before the first embed
and print its `build_info` with their result, the way `_served` in `test_thinking_switch_live.py`
reads and prints the generation server's; a later row in `ranked-recall.md` names that build. This
changes no shipped code and no port. A `GET /props` from `LlamaCppEmbedder`
([embedder.py](../../../brain/packages/embedding/src/cortex_embedding/embedder.py)), logged the way
the generation line is, would not reach these readings: the tests build their own
`LlamaCppEmbedder`, and pytest shows no log record of a passing test, since the brain's pytest
settings set no `log_cli`. That line serves a running stack whose recall changed after a pull, and
no such change has been recorded. Validating the print needs a live run against an embedder, so it waits for a card or
CPU set no measurement is using.

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
