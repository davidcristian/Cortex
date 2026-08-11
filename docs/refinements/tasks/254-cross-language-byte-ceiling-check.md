# A cross-language check on the byte ceiling

**Status:** landed 2026-08-03
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

`MAX_CAPTURE_BYTES` (Rust) and
`MAX_IMAGE_BYTES` (Python) are the same number, 6 MiB, and each is pinned to the literal
`6291456` by a test in its own toolchain. **Nothing mechanical couples them**: an edit to one
leaves both suites green. The wire's `max_bytes` hint removes most of the risk (the brain sends
its own budget and the body clamps to its ceiling, so a disagreement tightens rather than
breaks), but a repo-gate scan asserting the two literals match is the honest fix. It would live
beside `linecap.py` and `dashcheck.py` and cost one small script.

**Landed 2026-08-03 as `scripts/crosscheck.py`, and the entry was wrong about itself in a way
that sharpened the design ([ADR-0029 cross-language-constant addendum](../../adr/ADR-0029-vision-screen-capture.md)).**
"An edit to one leaves both suites green" is not what happens: measured rather than assumed,
raising `MAX_CAPTURE_BYTES` to 8 MiB alone fails `body-core`'s own suite at exit 101, because
that side's pin catches an edit to the constant. What actually drifts is an edit to the
constant **and** its own pin, which is the ordinary shape of a deliberate change to one side,
not a careless one. With both at 8 MiB, `cargo test -p body-core` and the brain's `packages/
core` and `packages/body_client` suites are all green while the two trees disagree by 2 MiB.
So a per-toolchain pin was not weak enforcement of the coupling; it was enforcement of the
wrong thing, since it can only compare a tree with itself. The cost estimate held: one small
script beside the other two, wired into `just check` and CI's unconditional `cross-tree` job.
What the entry did not anticipate is the shape. Rather than asserting one pair, the scan holds
a registry of constants, each naming two or more declaration sites, and compares the sites with
each other rather than against a master, so editing either side alone fails. The proto is
**not** that master, which the addendum argues from the code: protobuf has no constant, so a
number could sit there only as a comment, a third uncoupled copy of the kind the 1600 px
default edge already has four of. It fails closed on every way of not finding a value, since a
scan that cannot find its constants would agree with itself forever, and that was proven by
planting a rename, a deletion, and a moved file. A second entry rides along, the seam token's
metadata key, declared three times by hand with nothing comparing them; the survey behind that
choice, and the couplings deliberately left unregistered, are in
[repo-gates.md](../index.md#repo-gates).

## Trail

- 2026-07-18: opened with the vision slice.
- 2026-08-03: landed as `scripts/crosscheck.py`, the third cross-tree scan, moving the area's count
  18 to 17 and repo gates 4 to 5. It had been filed in the index under a heading about seam and port
  changes and needed no seam change at all, which the entry itself said. What incremented repo gates
  is the survey the registry shape forced: the seam token's metadata key rode along as a second
  registered constant, and everything else the survey found became a written deferral rather than an
  absence, in three kinds the scan could not hold that morning (ordered relations rather than
  equalities, values spelled inside strings, and TypeScript). One of them, `TITLE_MAX`, was already
  divergent at 48 against 32, so registering it then would have turned a gate on over a shipped
  disagreement nobody had decided how to resolve, and it waited on that decision rather than on the
  scanner. That decision was made later the same day, so the registry stood at three and the scan
  read TypeScript.
