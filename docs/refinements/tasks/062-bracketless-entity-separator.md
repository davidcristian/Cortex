# Bracketless HTML character reference separator

**Status:** done 2026-08-08
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

The leftover [R-061](061-fullwidth-cjk-punctuation-twins.md) named as its next pass. Measured the
same way first, through a real `TaintLedger` holding a collected `https://evil.example/pay` and a
real streaming filter fed one character at a time: `https&#58;//evil.example/pay` anchored no
match at all, so neither policy matched it.

Fixing the one measured form would have left ten, because the reference is a family: the decimal
and hexadecimal forms, zero-padded (`&#0058;`, `&#x003a;`) or not, with HTML's optional semicolon
or without, upper or lower case, the named `&colon;` and `&sol;`, and the solidi as well as the
colon. Every one of them was live, and every one is now generated from the character's codepoint
(`_entity_forms`), so a form nobody thought of is not the one that gets through. Mixtures with the
fullwidth glyphs come free, since the matcher composes the per-character alternations.

The renderer is what puts this on the closed side of the line
[R-061](061-fullwidth-cjk-punctuation-twins.md) drew. An HTML character reference is a text-layer
encoding a renderer resolves before anything looks for a URL, so an HTML email body reading
`https&#58;//evil.example` displays and autolinks the plain link and the reader decodes nothing,
while a source-code escape is resolved by a compiler that is not in the picture and a bracketless
percent-escape is resolved by nobody, since percent-decoding only runs inside a string already
recognized as a URL. That same one-rendering-pass rule keeps `&COLON;` out (HTML's named
references are case-sensitive, so the anchor scopes that alternative with `(?-i:…)`), keeps
`&#58123` out (one five-digit reference, so the forms without a semicolon have a digit-run guard)
and keeps `&amp;#58;` out (it renders as text).

`url_identity.py` did not change at all: the decode fixpoint already folded all of this and the
whole gap was that nothing reached it. The streaming hold-back grew the second branch it needed
(`_OPEN_SEP_RE`: a scheme word, then complete separator forms, then an unfinished reference, with
the leading `&` required so `database` is not held), checked at all 840 two-way split points of
the measurement's probes. Eleven tests, each reverted with `__pycache__` cleared and each
reversion verified applied; the first fixture written for the digit-run guard did not make it fail
and was replaced with one that does.

What stays deferred in [R-059](059-mixed-other-encodings.md): source-code escapes
(`evil\u002eexample`, `\x2e`, `\056`, `%u002e`, `\.`, `https:\/\/…`), a bracketless
percent-encoded separator or whole scheme (`https%3A//…`, `https%3A%2F%2F…`), and stacked
references (`&amp;#58;`).

## History

- 2026-08-08: Fixed (ADR-0058 decision 5). What closed was a row in a leftover list rather than an
  entry anyone had counted.
