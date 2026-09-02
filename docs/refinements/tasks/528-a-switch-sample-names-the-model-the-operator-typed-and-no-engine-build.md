# A switch sample names the model the operator typed and no engine build

**Status:** landed 2026-09-02
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-02 by the close of
[R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), which ran nine lineup picks
through the thinking-switch probe and carried each row's build and model file into the record by
hand.

The sample `brain/packages/inference/tests/test_thinking_switch_live.py` writes holds `model`,
which is `CORTEX_THINKING_MODEL` exactly as the operator set it, and `endpoint`, which is a URL.
Neither says which engine build served the run or which file the server had loaded. The same
server answers both on `GET /props`: `build_info` reads `b10680-d7bd3bfca` and `model_path` reads
`/models/unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf`, beside the `model_alias` the server
was started with. So the build and the quant a published row names are facts the sitting's driver
fetched in a separate call and typed into the ADR table, and a sample passed to `just switch-tail`
is published under whatever name the operator chose. The two rows measured at a quant ADR-0004
does not name are recorded as such only because the operator spelled the quant into the name.

**Why it was left.** The sweep was the task, and a new field is a change to the sample grammar:
`scripts/switchsamples.py` requires every field by name, so a sample written before the field
existed would stop loading, which is a decision about old samples (none are kept, `measurements/`
being gitignored by design) and a mutation table over the two suites that read the format. Neither
belonged inside a measurement pass.

**What would close it.** The probe reads `/props` once, before the cells, and writes the server's
`build_info` and `model_path` into the sample; `switchsamples.py` requires both; `switchtail.py`
prints them on the report's first line, so a published row is copied off the page rather than off
the driver's notes. The quant a row was measured at is then read off the path rather than off a
name, and a row measured at a quant the lineup does not name is visible in the report itself.

## Trail

- 2026-09-02: opened by the close of
  [R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), whose ADR-0005 lineup-tails
  addendum records the nine rows and the build each was read on.

- 2026-09-02: landed. Re-derived first, and every claim held: the sample carried `model` and
  `endpoint` and nothing the server said of itself, the reader required each field by name, no
  sample was kept, and the probe, the reader and the format had not moved since the quiet-control
  addendum. `GET /props` was read live off one CPU server and reports `build_info` and `model_path`
  beside `model_alias`, `model_ftype` and a context size. The probe now reads that route once,
  before anything is decoded, and writes `build_info` and `model_path` into the sample under the
  server's own names; `switchsamples.py` requires both; `switchtail.py` prints them on the report's
  second line, under the name the operator typed. Validated on a live Qwen3.5-0.8B server on the CPU
  image, five draws a cell, published at exit 0. Opened
  [R-535](535-a-switch-sample-names-no-context-size-or-placement.md), the placement column a row is
  still typed under. Recorded as the ADR-0005 served-by addendum.
