# A URL in fullwidth and CJK punctuation twins

**Status:** landed 2026-08-08
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

It was found while measuring the
encodings tail above rather than in it, and the tail it was found under stays open. Setting out
to price "mixed/other encodings past percent + HTML" against the shipped module turned up two
bypasses that are not encodings at all and are both worse than the tail being priced, each
reproduced end to end first through a real `TaintLedger` holding a collected
`https://evil.example/pay` and a real streaming filter fed one character at a time.
**A CJK-dotted host leaked past the default policy**: `https://evil。example/pay` (U+3002) and its
halfwidth twin (U+FF61) carried an identity the collected set did not hold, so redact mode passed
them and only strict mode caught them. Unlike every obfuscation closed before it this one asks the
reader to decode nothing, because the **resolver** does it: the stdlib's own IDNA codec splits a
host on exactly `.`, `。`, `．` and `｡` (`encodings.idna.dots`) and `"evil。example".encode("idna")`
is `b"evil.example"`, which is what makes the new fold a fact rather than the judgement the
curated confusable table beside it makes. NFKC covers the other two of the four (`．` and the
one-dot leader) but maps `｡` *onto* `。` rather than to a dot, so the pair it leaves standing is
exactly the pair that leaked. **And a fullwidth scheme separator matched nothing at all**:
`https：//evil.example/pay` (U+FF1A), `https:／／…` (U+FF0F) and `mailto：…` anchored no match, so
**both** policies were blind to them, the severe shape the seventh addendum's bracket asymmetry
had. The separator is the anchor and runs before any normalization, so NFKC folding those two
characters in the identity never helped; the colon and the solidus are now two-entry tables with
every spelling generated from them, the `_BRACKETS` precedent, so a mixed `https:／／` cannot be the
forgotten one. Grammar-and-identity only, no seam change, both policies inheriting it for free;
ten tests, mutation-proven in two groups (dropping the label-dot fold reddens four, shrinking the
separator tables reddens six). **The count does not move**, in either direction: nothing counted
here closed, and the two bypasses were never counted because nobody had named them, the same
treatment the seventh addendum's bracket asymmetry got. What the same run measured and did **not**
close is written into the tail entry above as the table it now carries: source-code escapes
(`evil\u002eexample`, `\x2e`, `\056`, `%u002e`, `\.`) still fold to nothing, and JSON-escaped
slashes, a whole percent-encoded scheme, and a bracket-less entity colon (`https&#58;//…`) anchor
nothing, deferred because a source-code escape is resolved by no renderer and no resolver, so
folding it is a bet on a reader decoding by hand and needs its own argument rather than a ride on
this one.

## Trail

- 2026-08-08: Landed as the eighth ADR-0015 addendum, found while pricing the encodings tail
  rather than in it. The index recorded the area's count deliberately unmoved, since neither
  bypass had ever been counted, nobody having named them.
