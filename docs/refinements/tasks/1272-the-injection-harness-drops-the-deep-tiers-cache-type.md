# The injection harness drops the deep tier's cache type

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)
**Verified:** 2026-11-21

ADR-0060 decision 1 says an injection row starts its server with the tier's own command line,
with the artifact, the port, the layer count and the tail substituted. For a tier that thinks,
`server_argv` in `brain/packages/inference/tests/test_injection_defense_live.py` builds the tail
from the tier's `--cache-ram` pair alone (`prompt_cache`), so every other flag of the tier's
`extra` is left out. The deep tier's `extra` has `--cache-type-k q8_0 --cache-type-v q8_0` since
its cache type default became `q8_0`, and a deployment that names a drafter adds the drafter's
flags there too.

Read on 2026-11-21:

- `server_argv` for the `Qwen3.8-27B (brain)` entry returns `-ngl 99 --ctx-size 16384 --parallel
  1 --jinja --cache-ram 0` and no cache type flag. The model host starts the same tier with
  `--cache-type-k q8_0 --cache-type-v q8_0` after those flags.
- `test_a_shipped_row_is_its_tiers_own_command_line` in `test_switch_rows.py` compares the two
  over `MODELS`, which has the deep candidates only when `CORTEX_PROBE_BRAIN` is set. CI does not
  set it, and the test passes. With `CORTEX_PROBE_BRAIN=1` it fails on `gemma-4-31B (brain)`:
  `Right contains 4 more items, first extra item: '--cache-type-k'`.
- The row starts from the `ghcr.io/ggml-org/llama.cpp:server-cuda` tag, and the model host is an
  image built from that tag earlier, so one machine can run the two on different engine builds.
  On the machine the rows of 2026-11-21 were drawn on, the tag's `llama-server --version` prints
  build 12169 and the model host's `/props` reports build 12375.

So the deep row of the
[injection probes runbook](../../runbooks/injection-probes.md#the-deep-tiers-row) counts a server
at the engine's 16-bit cache. The rows of 2026-11-21 were drawn on a deep server the model host
started instead ([injection text rows](../../readings/injection-text-rows.md)).

## What to do

- Keep the tier's cache type flags in the row of a tier that thinks: build its tail from the
  tier's `extra` with the row's own substitutions, or read the cache type flags off it the way
  `prompt_cache` reads the prompt cache pair.
- Compare the deep candidates in CI. `test_a_shipped_row_is_its_tiers_own_command_line` starts no
  server, so it can loop over `BRAIN_CANDIDATES` whether or not the flag is set.
- Decide whether a deep row drafts. A deployment names the drafter, so the harness has no default
  to read. The pick's rows of 2026-11-21 read 0 of 100 framed with the draft layer and without.
- Print the engine build a row ran on. `/props` reports it as `build_info`.

What would close it: the deep row's argv equal to the tier's with only the artifact and the port
changed, compared by a test CI runs, and that test seen to fail with the cache type left out.

## History

- 2026-11-21: filed by the injection rows at the shipped configuration
  ([R-1267](1267-qwen38-27bs-injection-row-was-drawn-at-8192-on-an-earlier-build.md)).
