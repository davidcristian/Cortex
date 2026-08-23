# The headroom suite spells the edge it now declares four more times, in prose and in an assertion

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-382](382-the-paired-numbers-quoted-in-prose.md), which promoted
`body/crates/core/tests/capture_bytes.rs` from a file nobody had read into a declaring site: its
`const BRAIN_EDGE: u32 = 2048` is now tied to the brain's `DEFAULT_CAPTURE_MAX_EDGE`.

That file spells the same number four more times without going through the constant. Its module
docstring opens "The brain asks for a 2048 px capture by default now" and explains a paragraph
later why "a 2048 px capture costs so" much; a comment inside the wallpaper case says the whole
desktop is "resampled to 2048 px"; and one assertion pins a resampled size as a bare pair,
`assert_eq!((width, height), (2048, 1152))`. The last is the one that matters most: it is derived
from the edge and written as a literal, so a retune moves `BRAIN_EDGE` and the crosscheck gate
stays green while that assertion fails in the Rust suite with a number nothing explains.

**Why it was left.** Registering prose in the file that declares the value is what the neighbouring
close already does twice over, so the two docstring sentences are rows and not decisions. The
assertion is not: `1152` is `2048 * 9 / 16` for the 4K display the case builds, so pinning the pair
as a mention would tie the edge and a derived height in one needle and would redden on a change to
the fixture's aspect ratio, which is a different coupling wearing the same digits. The honest fix
is probably arithmetic in the test rather than a registry row, and that is a change to the suite.

**What would close it.** Register the two docstring sentences and the comment. Then read the
assertion and decide whether the height should be computed from `BRAIN_EDGE` in the test, which
removes the coupling instead of holding it, or pinned with a comment saying which number it is
derived from. Check the sibling cases while there: the file's own header table and the halving
prose name pixel counts that are the edge's quarters and halves, and whether those are readings of
this constant or independent numbers is the question that decides how far this goes.

## Trail

- 2026-08-23: opened by the close of
  [R-382](382-the-paired-numbers-quoted-in-prose.md), which registered this file's constant and
  deliberately left the four spellings around it unsorted, the assertion being a code change rather
  than a row.
- 2026-08-23: landed as three mentions, one new two-site entry and one arithmetic change. **The
  count was right**, unlike the three sorts before it, and one claim was not: the entry names "the
  file's own header table" and that file has no table. The three sentences are far sides on the
  reading a declaring file's own prose already had; the byte reading in the body contract stays a
  control, and was re-run because the needle added here spells its words. **A derived literal is a
  consequence of a value and not a spelling of it**, so `(2048, 1152)` gets no row: the height is
  the edge times the fixture's aspect ratio, and a needle over the pair would redden when the
  fixture's display changed, naming a coupling that never moved. The case computes the size from
  the constants it declares instead, which removes the coupling rather than holding it, and the
  maximised window's rectangle now derives from `SOURCE` for the same reason. The same reading
  keeps the halved `1024` out, a rung below the edge being a consequence too, which answers this
  entry's closing question about quarters and halves. **The sibling was the un-halved number**:
  `BODY_EDGE` is the body's own `DEFAULT_MAX_EDGE` copied as a literal and held by nothing. It was
  registered as a two-site entry and **the registry's own suite refused it**, an entry whose places
  are all one language proving nothing about a seam, and that refusal was right: this suite already
  imports from the module that declares it, so the copy needed to stop being a copy rather than to
  gain a gate. `BODY_EDGE` is now that constant imported and the compiler holds it, which puts the
  line between the two edges at reach rather than importance. Its prose is deferred as a survey of
  seventy spellings ([R-399](399-the-body-edge-is-two-sites-and-no-prose.md)). Three planted drifts
  reddened crosscheck and one reddened the Rust suite alone, which is the entry's own argument
  measured:
  retuned to 1800 the literal pair fails with `left: (1800, 1012)` against `right: (2048, 1152)`
  and the derived pair passes. All four cases run green on the restored tree in 77 s. Tabled in the
  ADR-0029 second-spelling addendum.
