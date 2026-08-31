# A rendered integer is a whole token inside a decimal that begins with it

**Status:** landed 2026-08-24
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-387](387-a-second-spelling-shares-a-held-line.md), whose population reading tripped over this
while counting occurrences and had to be triaged by hand because of it.

`crosscheck.bounded` guards a rendered needle at each edge that is itself a word character, so
`50051` cannot be found inside `500511`. A decimal point is not a word character, so `10` **is**
found inside `10.09`: the lead guard reads a space and the trail guard reads a `.`, and both pass. In
the tree today this is harmless, because every template around an integer carries the variable's
own name, a unit or a table boundary, so nothing renders a bare number into a file that writes
decimals. It was still enough to make three of eleven readings in that survey false positives, on
`docs/runbooks/model-swap.md`, where a `10 s` grace sits beside latencies of `10.09 s` and
`10.90 s`.

**Why it was left.** It is a latent edge rather than a live one, and the fix is a judgement about
what a number's boundary is rather than a line. Treating `.` as a continuation would be wrong for
every needle that legitimately ends at a sentence's full stop, of which the registry has several,
and it would have to be wrong in a way that distinguishes `2048.` from `10.09`. The honest version looks
at what follows the point: a digit continues a number and anything else ends a sentence. That is a
real change to the matcher, with its own tests, made on a defect nothing in the tree currently
suffers, and doing it inside a close about second spellings would have hidden it.

**What would close it.** Decide whether the guard should read a digit after the point, and either
build it with a test that pins a needle rendering `10` against a file spelling `10.09` and nothing
else, or write down that it will not be built and why, which is a legitimate outcome: every
template in the registry carries something after the value, and a rule saying so is cheaper than a
matcher that reasons about decimals. If the second, the rule belongs where mention templates are
described rather than in the matcher, and it needs a registry invariant under which a template
rendering a value at its very end fails.

## Trail

- 2026-08-23: opened by the close of
  [R-387](387-a-second-spelling-shares-a-held-line.md), whose measurement of second spellings on
  held lines reported three occurrences that were a bounded integer sitting inside a decimal.
- 2026-08-24: landed as the guard this entry proposed, under the rule that **a point flanked by
  digits is inside a number**, which is one sentence read from both ends: a digit edge takes
  `(?<!\d\.)` or `(?!\.\d)` beside the word guard, and an edge that is a word but not a digit takes
  neither. The defect reproduced before it was fixed, `bounded("10")` over the swap runbook
  finding eight occurrences and now finding four, the four dropped being `10.89`, `10.09`, `10.90`
  and, the symmetric case this entry asked about and did not measure, `0.10` three lines below.
  **Both premises of the decline were wrong.** No needle in the registry ends at a point of any
  kind, so the several that "legitimately end at a full stop" were none; and the invariant the
  cheap outcome rested on, refusing a template that renders a value at its very end, would refuse
  27 of the 180 mentions. What the registry does have is the mirror image, three needles that begin
  just after a point (`grpc.insecure_channel(...)`), which is why the guard reads the far side of
  the point rather than the point itself. The verdict on the live tree does not move; what moves is
  the reading an unfound needle carries, proved live by retuning the stop grace to `11.0` and
  watching the swap runbook's fault stop claiming the file still spells `11` on the strength of a
  `11.3 s` latency. Five planted mutations, one of which survived its first pass and bought the two
  tests that kill it, tabled in the ADR-0029 decimal-edge addendum. One residue: that same value
  reading does not say **where** it read the value
  ([R-414](414-the-still-spelled-reading-does-not-say-where.md)).
