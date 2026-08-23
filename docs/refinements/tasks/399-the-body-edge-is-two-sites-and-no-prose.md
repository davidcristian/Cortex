# The body's own default edge is stated in prose that nothing reaches

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-388](388-the-headroom-suite-spells-its-own-constant.md), which found the headroom suite copying
this constant as a literal, closed that half with an import, and stopped there on purpose.

`DEFAULT_MAX_EDGE` in `body/crates/core/src/os/screen_policy.rs` is the edge a capture is
downscaled to when the caller asks for no particular size, and it is in no registry entry at all.
Every other edge and budget in `scripts/capturecouplings.py` carries the places that state it: a
compose default, a runbook row, a module contract. This one carries none, so the number a caller
gets when it asks for nothing can drift in every document that quotes it with the gate green.

The half that closed needed no registry row: the suite that copied it imports from the module that
declares it, so `BODY_EDGE` is now that constant rather than a second spelling of it, and the
compiler holds the pair. The registry's own suite is what said so, refusing an entry whose places
were both Rust. The prose is the other half, and it is untouched.

**Why it was left.** The survey is the size of the two this month rather than a clause in a close
about a different constant. `1600` is spelled **70 times in 29 files** outside the decision records
and the backlog, and unlike a port or a token budget most of those are not this value at all: a
Cargo lockfile checksum, a fixture's own choice of edge in `screen.rs` and `test_gateway.py`, a
corpus's render size, a byte count that happens to contain the digits. Sorting it means reading
seventy lines and deciding each, which is exactly the work the two port sorts and the legibility
sort each turned out to be, and each of those was a slice.

**What would close it.** Read the seventy by the tense test, the same one those three used: a
sentence that becomes wrong when the default moves is a far side, one that becomes history is not,
and a suite's own choice of edge is a fixture rather than either. The likely far sides are already
visible from the census and are few: `screen_policy.rs`'s own prose above the constant,
`proto/body.proto`'s comment on `max_edge`, `docs/modules/body-core.md`'s `DEFAULT_MAX_EDGE` (1600)
restatement, `docs/runbooks/vision.md`'s "hands the edge back to the body's own default (1600)",
`config_body.py`'s prose, and whatever `docs/runbooks/llamacpp-gpu.md`'s six turn out to be. Read
the fixtures out first, since they are the bulk and the whole reason this is a survey. The
population reading that sorted second spellings is the tool to reuse, and its own limits are
recorded ([R-397](397-nothing-counts-what-the-registry-does-not-name.md)).

## Trail

- 2026-08-23: opened by the close of
  [R-388](388-the-headroom-suite-spells-its-own-constant.md), which found this constant copied into
  the headroom suite while reading that file for the halved numbers, replaced the copy with an
  import, and left the seventy prose spellings for a survey of their own.
