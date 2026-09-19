# A switch sample names the model the operator typed and no engine build

**Status:** done 2026-09-02
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

The sample `brain/packages/inference/tests/test_thinking_switch_live.py` writes has `model`, which
is `CORTEX_THINKING_MODEL` exactly as the operator set it, and `endpoint`, which is a URL. Neither
says which engine build served the run or which file the server had loaded. The same server answers
both on `GET /props`: `build_info` reads `b10680-d7bd3bfca` and `model_path` reads
`/models/unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf`, beside the `model_alias` the server
was started with. So the build and the quant a published row names are facts fetched in a separate
call and typed into the ADR table, and a sample passed to `just switch-tail` is published under
whatever name the operator chose.

## History

- 2026-09-02: opened by the close of
  [R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), which ran nine lineup picks
  through the thinking-switch probe and copied each row's build and model file into the record by
  hand.
- 2026-09-02: closed. Every claim held: the sample had `model` and `endpoint` and nothing the server
  said of itself, the reader required each field by name, no sample was kept, and the probe, the
  reader and the format had not moved. `GET /props` was read live off one CPU server and reports
  `build_info` and `model_path` beside `model_alias`, `model_ftype` and a context size. The probe
  now reads that route once, before anything is decoded, and writes `build_info` and `model_path`
  into the sample under the server's own names; `switchsamples.py` requires both; `switchtail.py`
  prints them on the report's second line, under the name the operator typed. Validated on a live
  Qwen3.5-0.8B server on the CPU image, five draws a cell, published at exit 0. Opened
  [R-535](535-a-switch-sample-names-no-context-size-or-placement.md). Recorded as ADR-0050.
