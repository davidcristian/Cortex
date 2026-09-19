# The body's own default edge is stated in prose that nothing checks

**Status:** done 2026-08-25
**Area:** repo-checks
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`DEFAULT_MAX_EDGE` in `body/crates/core/src/os/screen_policy.rs` is the edge a capture is
downscaled to when the caller asks for no particular size, and it is in no registry entry. Every
other edge and budget in `scripts/capturecouplings.py` lists the places that state it: a compose
default, a runbook row, a module contract. This one lists none, so the number a caller gets when it
asks for nothing can change in every document that quotes it with the check still passing.

The other half closed without a registry row: the suite that copied the number imports from the
module that declares it, so `BODY_EDGE` is that constant rather than a second copy, and the
compiler enforces the pair. The registry's own suite reported it, failing on an entry whose places
were both Rust.

The prose is a survey rather than a row. `1600` appears 70 times in 29 files outside the decision
records and the backlog, and most of those are not this value: a Cargo lockfile checksum, a
fixture's own choice of edge in `screen.rs` and `test_gateway.py`, a corpus's render size, a byte
count that happens to contain the digits. Sorting it means reading seventy lines and deciding each.

## History

- 2026-08-23: opened by the close of
  [R-388](388-the-headroom-suite-spells-its-own-constant.md), which found this constant copied into
  the headroom suite, replaced the copy with an import, and left the seventy prose occurrences for
  a survey of their own.
- 2026-08-25: closed as one entry, one declaration and seventeen matches across eleven files. The
  count was exact and the list was half of what is there. `1600` really does appear 70 times
  outside the decision records and the backlog, in thirty files rather than twenty nine, and it was
  thirty on the day this was written. But the entry's likely places top out at eleven and the tree
  has seventeen, with five files it never names holding six of them: `capture_bytes.rs`'s two prose
  sentences, `images.py`'s byte comment, `test_config.py`'s comment, the body override's compose
  comment and [modules/brain-orchestrator.md](../../modules/brain-orchestrator.md). Of the GPU
  runbook's six, four are this edge and two are a `max_tokens` budget. Two rules were sharpened
  rather than invented. First, for a number quoted as often as it is measured at: naming this edge
  as what the body returns is a registrable place, naming it as the size a measurement was taken at
  is a record of the past, which covers four of the GPU runbook's sentences and leaves the vision
  runbook's dated reading, the two byte readings at 1600x900 and the shrink ladder's arithmetic
  out. Second, the suite rule, which this is the first case to test at its edge: a suite CI runs
  covers what it asserts, so `screen.rs` and `body_server.rs` stay out and `test_config.py`'s
  comment, which no assertion reaches and no Python can import, comes in. Thirty one of the seventy
  are a fixture's own choice of size and twelve are another value entirely. One more was removed
  instead of registered: `crosscheck.py`'s docstring claimed this edge already appeared in four
  places, a census the check had no business quoting and which was wrong by sixty six. Eighteen
  planted changes each made the check fail, seventeen of them one fault each and the declaration
  seventeen at once, with nine controls green and three Rust plantings failing in the two suites
  that assert the number. Two residues filed: the injection corpus calls its render size the body's
  own output and nothing ties it to one
  ([R-427](427-the-injection-corpus-claims-a-size-nothing-holds.md)), and the proto comment now
  covered has a generated twin nothing compares against the proto
  ([R-428](428-nothing-compares-the-committed-stubs-with-the-proto.md)).
