# The seam-stub check reads one direction, and only one of the two stubs

**Status:** landed 2026-08-25
**Area:** seam-transport
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)

Opened 2026-08-25 by the close of
[R-428](428-nothing-compares-the-committed-stubs-with-the-proto.md), which measured what each
candidate check catches and shipped the one that catches the silent case.

`stubcheck.py` holds every comment [proto/body.proto](../../../proto/body.proto) carries to the
committed Rust stub. That direction is the one that matters, because it is the direction a
forgotten regeneration breaks: the proto moves on and the generated copy states the old thing.
Three gaps are left open, and all three are recorded here rather than left to be rediscovered.
The third was found by the mutation table rather than designed for: tonic emits each service
banner **twice**, once into the client module and once into the server, so rewording one of the
two copies in the stub leaves the other answering for it and the gate stays green. A comment
present anywhere in the stub satisfies the rule, because the rule is containment rather than
correspondence, and making it decide which copy belongs to which declaration means giving it a
model of the stub's structure, which is most of the way to parsing generated Rust.

The first is **the other direction**. A comment deleted from the proto but still present in the
stub passes, because every comment the proto now carries is still found. That is a stale stub
too, and it is the same defect with the opposite sign. It was left because the reverse
comparison is not symmetric to write: the stub carries doc comments `prost` synthesizes rather
than copies, `Nested message and enum types in ...` among them, so a naive reverse check has
false positives that need their own list of exceptions, and a list of exceptions is a place for
a real staleness to hide.

The second is **the Python stubs, which nothing holds at all**. They carry no comments, so this
gate has nothing to compare, and the measurement behind the close showed why that is tolerable
rather than fine: regenerating them is free, reproduces byte for byte, and sees only structural
drift, which mostly fails on its own. Mostly is not always. A message or field added to
the proto and never regenerated is invisible until somebody writes code against it, and the
error it then produces names the missing attribute rather than the skipped regeneration.

**Why it was left.** The close was about choosing between a cheap check and an expensive one on
evidence, and both of these are refinements of the cheap one rather than reversals of that
choice. Neither is urgent while `just proto` regenerates both stacks together, which makes the
realistic failure a proto edit with no regeneration at all, and that is exactly what the shipped
gate catches.

**What would close it.** For the doubled banner: decide whether counting occurrences is worth it,
which means the gate would need an expected number of copies for a given comment, and that
number comes from the stub's own shape. For the direction: decide whether a reverse comparison
with a named, argued list of `prost` synthesized comments is better than no reverse comparison,
and be honest that the list is the risk. For the Python stubs: the regenerate-and-diff inside
`check-brain` is
known to work and known to need no new toolchain, so this is a decision about whether a check
that only catches the quiet half of structural drift earns a codegen run on every brain change.
Measure how long that run takes before arguing either way.

## Trail

- **2026-08-25, closed.** All three gaps settled, one closed and two declined, argued in the
  ADR-0003 addendum on counted copies. **The entry was wrong about the first one's cost**: it
  said giving the gate a count of copies to expect means giving it a model of the stub's structure, and
  the number turned out to come from the **proto's** shape, which the reader already walks. A
  comment inside a `service` block, or in the unbroken run directly above the `service` line, is
  owed two copies; every other comment is owed one; the rule moved from set containment to a tally
  comparison and a miss now names both numbers. Measured against the tree: 208 proto comments, 72
  of them claimed by a service, all present in at least the copies they are owed. One text is
  pinned to a floor of one rather than counted, the rule line, because prost absorbs a banner's
  closing rule into the heading above it, so four written rules come out as four copies and not
  eight; that was measured, not assumed. The reverse direction is declined because its exception
  list for prost-synthesized comments is a permanent hiding place, bought against a dead paragraph
  in generated code nobody hand-edits. The Python regenerate-and-diff is declined again, now with
  the timing the entry asked for: 0.08s, so cost was never the argument, and what it buys is drift
  a compiler and pyright already report. **Nineteen mutations over the gate against the real
  proto and the real stub, all as designed, and twelve mutants over the gate's own 67 tests, all
  killed**, both tabled in that addendum. Row 07, the doubled banner, was green before this and
  fails now.
