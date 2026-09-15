# A switch sample names no context size or placement

**Status:** landed 2026-09-15
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-02 by the close of
[R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md), which
wrote the engine build and the model file a server reports on `GET /props` into the sample the
thinking-switch probe writes.

A sample now names the build and the file that served it, and the lineup-tails record's placement
column, `-ngl 99 -c 8192` a row, is still typed by hand off the shell loop that started each
server. `GET /props` answers half of it. `default_generation_settings.n_ctx` reads the context size,
8192 on the server the close was validated against, and `model_ftype` reads the quant type, `Q8_0`
there, while the GPU layer count is on no route the server offers, so `-ngl` cannot be read back at
all. The record holds placement to be not a variable for this probe, the Qwen3.5-4B having read
identical cells both ways, so a placement typed wrong changes no verdict. What it changes is whether
a row's two hand-typed columns can be checked against anything.

**Why it was left.** The close kept to the two fields the entry named, and the context size is the
one field of the three a route reports. A sample field that carries half of a placement under a
name suggesting the whole of it is a field a reader trusts further than it reaches, and how the
sample should say that the layer count is unrecorded rather than zero is a grammar decision the
close did not take.

**What would close it.** The probe writes `n_ctx` off `default_generation_settings` beside
`build_info` and `model_path`, `switchsamples.py` requires it, the reader prints it on the served-on
line, and the lineup-tails record's placement column says which half of it a sample can confirm.
The layer count stays typed by hand unless a later build reports it.

## Trail

- 2026-09-02: opened by the close of
  [R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md), whose
  ADR-0005 served-by addendum records what `GET /props` reports and what it does not.

- 2026-09-04: re-derived and still open. The trigger names the sweep
  [R-529](529-the-rendering-column-is-one-builds-sweep-and-an-engine-bump-reopens-it.md) waits for,
  and that sweep has not been run: this stack still starts `build 10680, commit d7bd3bfca`, the
  build the lineup was read on. The second half of the trigger, a row whose verdict moves between
  placements, is unchanged too, no row having been read at a second placement since. The ADR-0005
  engine-tag addendum records what the engine tags now resolve to.

- 2026-09-13: the trigger has still not fired, on either limb. The sweep it waits on is
  [R-529](529-the-rendering-column-is-one-builds-sweep-and-an-engine-bump-reopens-it.md)'s, and the
  cached engine digests are unchanged, so no bump has reopened the lineup; no row has been read at
  a second placement either. The model host's tiers gained a stated host-RAM prompt cache size
  tonight, a per-tier number that is not the placement this entry is about: the record's placement
  column is still the layer count and context size of a scratch shell loop that starts one server
  per pick, and nothing in that loop reads `n_ctx` back off `GET /props` yet.

- 2026-09-15: landed. The probe reads `default_generation_settings.n_ctx` off `GET /props` beside
  `build_info` and `model_path`, writes it into the sample under that name, `switchsamples.py`
  requires it as a count, and `switchtail.py` prints it on the served-on line, which now reads
  `served on <build> from <file> at <n> tokens of context`. The lineup-tails record's placement
  column keeps both figures and says which of them a sample confirms: the context size, since the
  GPU layer count is on no route llama-server offers. Recorded end to end on one server on
  `b10680-d7bd3bfca` serving `Qwen3.5-0.8B-Q8_0.gguf` at `-ngl 99 -c 8192`, whose sample came back
  carrying `n_ctx` 8192 and published at exit 0. The nine samples of the 2026-09-02 sweep still on
  this host were already unreadable, having been written before a sample carried `build_info`, so
  the required field costs them nothing. The ADR-0005 context-size addendum carries the run and the
  mutation table.
