# A URL in fullwidth and CJK punctuation twins

**Status:** done 2026-08-08
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

Two bypasses found while pricing [R-059](059-mixed-other-encodings.md), neither of them an
encoding. Each was reproduced end to end first, through a real `TaintLedger` holding a collected
`https://evil.example/pay` and a real streaming filter fed one character at a time.

A CJK-dotted host leaked past the default policy: `https://evil。example/pay` (U+3002) and its
halfwidth twin (U+FF61) had an identity the collected set did not hold, so redact mode passed them
and only strict mode caught them. Unlike every earlier case the reader decodes nothing, because
the resolver does it: the stdlib's IDNA codec splits a host on exactly `.`, `。`, `．` and `｡`
(`encodings.idna.dots`), and `"evil。example".encode("idna")` is `b"evil.example"`. NFKC covers
two of the four (`．` and the one-dot leader) but maps `｡` onto `。` rather than to a dot, so the
pair it leaves unfolded is exactly the pair that leaked.

A fullwidth scheme separator matched nothing at all: `https：//evil.example/pay` (U+FF1A),
`https:／／…` (U+FF0F) and `mailto：…` anchored no match, so neither policy matched them. The
separator is the anchor and runs before any normalization, so folding those two characters in the
identity would never have helped. The colon and the solidus are now two-entry tables with every
form generated from them, following the `_BRACKETS` precedent, so a mixed `https:／／` cannot be
the forgotten one.

Grammar and identity only, no port change, both policies inheriting it. Ten tests, checked in two
groups: dropping the label-dot fold makes four fail, shrinking the separator tables makes six
fail.

What the same run measured and did not close went into [R-059](059-mixed-other-encodings.md) as
the list it then held: source-code escapes (`evil\u002eexample`, `\x2e`, `\056`, `%u002e`,
`\.`) still fold to nothing, and JSON-escaped slashes, a whole percent-encoded scheme and a
bracketless entity colon (`https&#58;//…`) anchor nothing. Those were deferred because a
source-code escape is resolved by no renderer and no resolver, so folding it assumes a reader
decoding by hand and needs its own argument.

## History

- 2026-08-08: Fixed (ADR-0058 decision 5), found while pricing the encodings entry rather than in
  it. Neither bypass had ever been counted, nobody having named them.
