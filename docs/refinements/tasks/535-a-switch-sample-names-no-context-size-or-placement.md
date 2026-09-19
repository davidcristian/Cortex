# A switch sample names no context size or placement

**Status:** done 2026-09-15
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

The sample written by the thinking-switch probe named the engine build and the model file the server
reports on `GET /props`, but not the placement the lineup-tails record prints beside each row
(`-ngl 99 -c 8192`), which was typed by hand. `GET /props` reports half of that placement:
`default_generation_settings.n_ctx` is the context size and `model_ftype` the quant type, while the
GPU layer count is on no route llama-server offers. The record treats placement as not a variable
for this probe, the Qwen3.5-4B having read identical cells both ways, so a placement typed wrong
changes no result. What it changes is whether a row's two hand-typed columns can be checked against
anything.

## History

- 2026-09-02: opened by the close of
  [R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md), which
  recorded what `GET /props` reports and what it does not (ADR-0050 decision 5).
- 2026-09-04: checked again and still open. The engine bump that
  [R-529](529-the-rendering-column-is-one-builds-sweep-and-an-engine-bump-reopens-it.md) waits for
  has not happened, since this stack still starts `build 10680, commit d7bd3bfca`, and no row has
  been read at a second placement.
- 2026-09-13: still open on both counts. The cached engine digests are unchanged and no row has been
  read at a second placement. The model host's tiers gained a host-RAM prompt cache size, which is a
  different number from the placement this entry is about.
- 2026-09-15: done. The probe reads `default_generation_settings.n_ctx` off `GET /props` beside
  `build_info` and `model_path` and writes it into the sample under that name, `switchsamples.py`
  requires it as a count, and `switchtail.py` prints it on the served-on line, which now reads
  `served on <build> from <file> at <n> tokens of context`. The lineup-tails record keeps both
  figures and says which one a sample confirms: the context size, since the GPU layer count is on no
  route. Checked end to end on one server on `b10680-d7bd3bfca` serving `Qwen3.5-0.8B-Q8_0.gguf` at
  `-ngl 99 -c 8192`, whose sample came back with `n_ctx` 8192 and published at exit 0. The nine
  samples from 2026-09-02 still on this host were already unreadable, having been written before a
  sample had `build_info`, so the new required field costs them nothing. The mutation table is in
  the commit.
