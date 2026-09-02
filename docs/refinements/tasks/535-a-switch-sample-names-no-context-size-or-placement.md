# A switch sample names no context size or placement

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** the next lineup sweep under an engine bump, which is the sweep R-529 waits for, when
the placement column of the lineup-tails record is typed by hand again for eleven rows; or a row
whose verdict moves between placements, which the record so far says does not happen.
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
