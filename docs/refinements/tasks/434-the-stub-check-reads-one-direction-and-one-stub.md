# The stub check reads one direction, and only one of the two stubs

**Status:** done 2026-08-25
**Area:** rpc-transport
**Origin:** [ADR-0003](../../adr/ADR-0003-generated-stubs.md)

`stubcheck.py` requires every comment `proto/body.proto` contains to appear in the committed Rust
stub. That is the direction a forgotten regeneration breaks: the proto moves on and the generated
copy states the old thing. Three gaps are left open.

The doubled banner. tonic emits each service banner twice, once into the client module and once
into the server, so rewording one of the two copies in the stub leaves the other satisfying the
rule. A comment present anywhere in the stub passes, because the rule is containment rather than
correspondence, and deciding which copy belongs to which declaration means giving the check a model
of the stub's structure.

The other direction. A comment deleted from the proto but still present in the stub passes, because
every comment the proto now has is still found. That is a stale stub too. The reverse comparison is
not symmetric to write: the stub contains doc comments `prost` synthesizes rather than copies,
`Nested message and enum types in ...` among them, so a naive reverse check has false positives
that need their own exception list, and an exception list is a place for a real staleness to hide.

The Python stubs, which nothing compares at all. They have no comments, so this check has nothing
to compare, and the measurement behind the close showed why that is tolerable rather than fine:
regenerating them is free, reproduces byte for byte, and sees only structural differences, which
mostly fail on their own. Mostly is not always. A message or field added to the proto and never
regenerated is invisible until somebody writes code against it.

## History

- 2026-08-25: opened by the close of
  [R-428](428-nothing-compares-the-committed-stubs-with-the-proto.md), which measured what each
  candidate check catches and shipped the one that catches the unreported case.
- 2026-08-25: closed. All three gaps settled, one fixed and two declined, argued in ADR-0003
  (decision 8 and its alternatives). The entry was wrong about the first one's cost: it said giving
  the check a count of copies to expect means giving it a model of the stub's structure, and the
  number turned out to come from the proto's shape, which the reader already walks. A comment
  inside a `service` block, or in the unbroken run directly above the `service` line, is owed two
  copies; every other comment is owed one; the rule moved from set containment to a tally
  comparison and a miss now names both numbers. Measured against the tree: 208 proto comments, 72
  of them claimed by a service, all present in at least the copies they are owed. One text has a
  minimum of one rather than a count, the rule line, because prost absorbs a banner's closing rule
  into the heading above it, so four written rules come out as four copies and not eight; that was
  measured, not assumed. The reverse direction is declined because its exception list for
  prost-synthesized comments is a permanent hiding place, bought against a dead paragraph in
  generated code nobody hand-edits. The Python regenerate-and-diff is declined again, now with the
  timing the entry asked for: 0.08s, so cost was never the argument, and what it buys is a
  difference a compiler and pyright already report. Nineteen mutations over the check against the
  real proto and the real stub, all as designed, and twelve mutants over the check's own 67 tests,
  all killed. The doubled banner, passing before this, fails now.
