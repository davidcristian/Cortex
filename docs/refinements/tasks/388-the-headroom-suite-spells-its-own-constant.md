# The headroom suite writes the edge it now declares four more times

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

[R-382](382-the-paired-numbers-quoted-in-prose.md) promoted
`body/crates/core/tests/capture_bytes.rs` from a file nobody had read into a declaring file: its
`const BRAIN_EDGE: u32 = 2048` is now tied to the brain's `DEFAULT_CAPTURE_MAX_EDGE`.

That file writes the same number four more times without going through the constant. Its module
docstring opens "The brain asks for a 2048 px capture by default now" and explains a paragraph
later why "a 2048 px capture costs so" much; a comment inside the wallpaper case says the whole
desktop is "resampled to 2048 px"; and one assertion fixes a resampled size as a bare pair,
`assert_eq!((width, height), (2048, 1152))`. The last matters most: it is derived from the edge
and written as a literal, so a retune moves `BRAIN_EDGE`, the cross-tree check still passes, and
that assertion fails in the Rust suite with a number nothing explains.

The two docstring sentences and the comment are ordinary registry rows. The assertion is not:
`1152` is `2048 * 9 / 16` for the 4K display the case builds, so matching the pair would tie the
edge and a derived height in one search text and would fail on a change to the fixture's aspect
ratio. The better fix is arithmetic in the test, which is a change to the suite.

## History

- 2026-08-23: opened by the close of
  [R-382](382-the-paired-numbers-quoted-in-prose.md), which registered this file's constant and
  left the four occurrences around it unsorted.
- 2026-08-23: closed as three matches, one new two-place entry and one arithmetic change. The
  count was right, unlike the three sortings before it, and one claim was not: the entry names
  "the file's own header table" and that file has no table. The three sentences are registrable on
  the reading a declaring file's own prose already had; the byte reading in the body contract
  stays a control, and was re-run because the search text added here includes its words. A derived
  literal is a consequence of a value and not another occurrence of it, so `(2048, 1152)` gets no
  row: the height is the edge times the fixture's aspect ratio, and a search text over the pair
  would fail when the fixture's display changed. The case computes the size from the constants it
  declares instead, which removes the coupling rather than checking it, and the maximised window's
  rectangle now derives from `SOURCE` for the same reason. The same reading keeps the halved
  `1024` out, a value one halving below the edge being a consequence too, which answers this
  entry's closing question about quarters and halves. The sibling was the un-halved number:
  `BODY_EDGE` is the body's own `DEFAULT_MAX_EDGE` copied as a literal and checked by nothing. It
  was registered as a two-place entry and the registry's own suite failed on it, since an entry
  whose places are all one language proves nothing about the boundary between the two trees, and
  that failure was right: this suite already imports from the module that declares it, so the copy
  needed to stop being a copy. `BODY_EDGE` is now that constant imported and the compiler enforces
  it. Its prose is deferred as a survey of seventy occurrences
  ([R-399](399-the-body-edge-is-two-sites-and-no-prose.md)). Three planted changes made crosscheck
  fail and one made the Rust suite alone fail, which is this entry's own argument measured: retuned
  to 1800, the literal pair fails with `left: (1800, 1012)` against `right: (2048, 1152)` and the
  derived pair passes. All four cases run green on the restored tree in 77 s.
