# A rendered integer is a whole token inside a decimal that begins with it

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** A registered integer whose template does not carry a name, a unit or a punctuation
mark right after the value, in a file that also writes decimals.

Opened 2026-08-23 by the close of
[R-387](387-a-second-spelling-shares-a-held-line.md), whose population reading tripped over this
while counting occurrences and had to be triaged by hand because of it.

`crosscheck.bounded` guards a rendered needle at each edge that is itself a word character, so
`50051` cannot be found inside `500511`. A decimal point is not a word character, so `10` **is**
found inside `10.09`: the lead guard sees a space and the trail guard sees a `.`, and both pass. In
the tree today this is harmless, because every template around an integer carries the variable's
own name, a unit or a table wall, so nothing renders a bare number into a file that writes
decimals. It was still enough to make three of eleven readings in that survey false positives, on
`docs/runbooks/model-swap.md`, where a `10 s` grace sits beside latencies of `10.09 s` and
`10.90 s`.

**Why it was left.** It is a latent edge rather than a live one, and the fix is a judgement about
what a number's boundary is rather than a line. Treating `.` as a continuation would be wrong for
every needle that legitimately ends at a sentence's full stop, of which the registry has several,
and it would have to be wrong in a way that can tell `2048.` from `10.09`. The honest version looks
at what follows the point: a digit continues a number and anything else ends a sentence. That is a
real change to the matcher, with its own tests, made on a defect nothing in the tree currently
suffers, and doing it inside a close about second spellings would have hidden it.

**What would close it.** Decide whether the guard should read a digit after the point, and either
build it with a test that pins a needle rendering `10` against a file spelling `10.09` and nothing
else, or write down that it will not be built and why, which is a legitimate outcome: every
template in the registry carries something after the value, and a rule saying so is cheaper than a
matcher that reasons about decimals. If the second, the rule belongs where mention templates are
described rather than in the matcher, and it wants a registry invariant that a template rendering
a value at its very end is refused.

## Trail

- 2026-08-23: opened by the close of
  [R-387](387-a-second-spelling-shares-a-held-line.md), whose measurement of second spellings on
  held lines reported three occurrences that were a bounded integer sitting inside a decimal.
