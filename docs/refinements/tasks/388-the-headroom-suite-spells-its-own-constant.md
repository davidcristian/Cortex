# The headroom suite spells the edge it now declares four more times, in prose and in an assertion

**Status:** open, actionable
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
