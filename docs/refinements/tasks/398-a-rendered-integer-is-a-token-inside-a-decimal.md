# A rendered integer matches as a whole token inside a decimal that begins with it

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`crosscheck.bounded` guards a rendered search text at each edge that is itself a word character, so
`50051` cannot be found inside `500511`. A decimal point is not a word character, so `10` is found
inside `10.09`: the leading guard reads a space and the trailing guard reads a `.`, and both pass.
In the tree today this is harmless, because every template around an integer includes the
variable's own name, a unit or a table boundary, so nothing renders a bare number into a file that
writes decimals. It was still enough to make three of eleven readings in that survey false
positives, on `docs/runbooks/model-swap.md`, where a `10 s` grace sits beside latencies of
`10.09 s` and `10.90 s`.

The fix is a judgement about what a number's boundary is. Treating `.` as a continuation would be
wrong for every search text that legitimately ends at a sentence's full stop, and it would have to
distinguish `2048.` from `10.09`. The accurate version looks at what follows the point: a digit
continues a number and anything else ends a sentence. That is a real change to the matcher, with
its own tests, on a defect nothing in the tree currently suffers.

## History

- 2026-08-23: opened by the close of
  [R-387](387-a-second-occurrence-shares-a-line-the-registry-covers.md), whose measurement of second occurrences on
  covered lines reported three hits that were a bounded integer inside a decimal.
- 2026-08-24: closed as the guard this entry proposed, under the rule that a point between two
  digits is inside a number, read from both ends: a digit edge takes `(?<!\d\.)` or `(?!\.\d)`
  beside the word guard, and an edge that is a word character but not a digit takes neither. The
  defect reproduced before it was fixed, `bounded("10")` over the swap runbook finding eight
  occurrences and now finding four, the four dropped being `10.89`, `10.09`, `10.90` and, the
  symmetric case this entry asked about and did not measure, `0.10` three lines below. Both
  premises of the decline were wrong. No search text in the registry ends at a point of any kind,
  so the several that "legitimately end at a full stop" were none; and the rule the cheap outcome
  rested on, refusing a template that renders a value at its very end, would refuse 27 of the 180
  matches. What the registry does have is the mirror image, three search texts that begin just
  after a point (`grpc.insecure_channel(...)`), which is why the guard reads the far side of the
  point rather than the point itself. The result on the live tree does not move; what moves is the
  reading an unmatched search text produces, proved live by retuning the stop grace to `11.0` and
  watching the swap runbook's message stop claiming the file still writes `11` on the strength of a
  `11.3 s` latency. Five planted mutations, one of which survived its first pass and bought the two
  tests that kill it. One residue: that same value reading does not say where it read the value
  ([R-414](414-the-still-contains-reading-does-not-say-where.md)).
