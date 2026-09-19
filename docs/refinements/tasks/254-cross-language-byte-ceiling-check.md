# A cross-language check on the byte ceiling

**Status:** done 2026-08-03
**Area:** vision
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`MAX_CAPTURE_BYTES` (Rust) and `MAX_IMAGE_BYTES` (Python) are the same number, 6 MiB, and each is
asserted against the literal `6291456` by a test in its own toolchain, with nothing comparing the
two. The wire's `max_bytes` hint removes most of the risk, since the brain sends its own budget and
the body clamps it, so a disagreement tightens rather than breaks, but a repo check comparing the
two literals is the real fix.

Done 2026-08-03 as `scripts/crosscheck.py`
([ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)). The entry was wrong about itself
in a way that improved the design. "An edit to one leaves both suites passing" is not what happens:
raising `MAX_CAPTURE_BYTES` to 8 MiB alone fails `body-core`'s own suite at exit 101, because that
side's test catches an edit to the constant. What actually diverges is an edit to the constant
together with its own test, which is the ordinary shape of a deliberate change to one side. With
both at 8 MiB, `cargo test -p body-core` and the brain's `packages/core` and `packages/body_client`
suites all pass while the two trees disagree by 2 MiB. So a per-toolchain test was not weak
enforcement of the coupling; it enforced the wrong thing, since it can only compare a tree with
itself.

The cost estimate held: one small script beside `linecap.py` and `dashcheck.py`, wired into `just
check` and CI's unconditional cross-tree job. What the entry did not anticipate is the shape. The
check keeps a registry of constants, each naming two or more places the value is written, and
compares those places with each other rather than against a master, so editing either side alone
fails. The proto is not that master, because protobuf has no constant, so a number could sit there
only as a comment, which would be a third uncoupled copy. It fails when it cannot find a value at
all, since a check that cannot find its constants would agree with itself forever, proven by
planting a rename, a deletion and a moved file. A second constant was registered at the same time,
the gRPC token's metadata key, written three times by hand with nothing comparing them. The survey
behind that choice, and the couplings deliberately left out, are in
[repo-checks.md](../index.md#repo-checks).

## History

- 2026-07-18: Opened with the vision slice.
- 2026-08-03: Done as `scripts/crosscheck.py`, the third cross-tree check, and it needed no change
  to the gRPC boundary at all. The survey the registry shape forced turned up three kinds of
  coupling the check could not handle that morning: ordered relations rather than equalities,
  values written inside strings, and TypeScript. One of them, `TITLE_MAX`, was already divergent at
  48 against 32, so registering it would have turned a check on over a shipped disagreement nobody
  had decided how to resolve. That decision was made later the same day, so the registry ended at
  three constants and the check read TypeScript.
