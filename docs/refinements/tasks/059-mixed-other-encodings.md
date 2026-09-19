# Mixed and other encodings past percent and HTML

**Status:** done 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

Left behind by [R-056](056-output-guardrail.md). Its two halves answered differently, and pricing
them apart is what closed it.

Mixed encodings were already free, and the measurement says how free: no position in this grammar
was ever a list of whole separators, each being an alternation generated per character, so every
combination of the colon's 9 forms and the solidus's 17 across both authority slashes, 2,601 in
all, folds to the one identity. The 306 that do not fold decline correctly: a hexadecimal
reference without a semicolon in front of a host whose first letter is a hex digit (`&#x2Fevil`)
is one three-digit reference and not a solidus, which is the entity family's own rule holding.

Other encodings owed one candidate, and the one that answers yes is the absence of a character
rather than an encoding of one: a URL parser removes every ASCII tab and newline from its input
before it parses anything, at every position, so `http://evil.exa<TAB>mple/pay` is the plain link
to every conforming parser, including the browser the user pastes into, and the overlay's
`white-space: pre-wrap` bubble hands the character to the clipboard intact.

The tab closed and the line break declined, on one measurement over the repo's own prose: 1,054
files, 1,348,844 words, 1,469 spans, with the tab adding, losing and extending nothing, and the
newline extending 42 spans over a line's end and into the next line's first word. That decline was
already argued when the split host's space table left the line-breaking family out, so this pass
only put a number to it.

The pass also fixed the one ordering decision the fold makes: a tab between two labels keeps the
gap reading (`evil.com`, the reader's) rather than the parser's (`evildotcom`), because the whole
defang family rests on the reader, so the removal runs after the gap fold and the host classes
keep excluding the character that the body now admits. Eleven tests, each reverted with
`__pycache__` cleared and each reversion verified applied, and the streaming needed no hold-back
branch of its own, checked at every two-way split point of nine probes under all three policies
(1,299 splits).

It leaves one entry behind: [R-285](285-a-tab-inside-a-scheme-word.md), the same character inside
the scheme word or its separator, which anchors nothing today.

## History

- 2026-08-08: Pricing this against the shipped module found source-code escapes
  (`evil\u002eexample`, `\x2e`, `\056`, `%u002e`, `\.`) folding to nothing, and JSON-escaped
  slashes, a whole percent-encoded scheme and a bracketless entity colon (`https&#58;//…`)
  anchoring nothing. The same run found two bypasses that were not in this list and fixed them.
- 2026-08-08: The bracketless entity colon closed the same day, as a whole family generated per
  character from its codepoint, on the distinction that a renderer resolves an HTML reference
  before anything looks for a URL.
- 2026-08-09: A review of deferred triggers ran against the tree and none fired.
- 2026-08-10: The remaining list was priced whole by asking of each row whether a resolver in this
  system's path turns the form back into the attacker's URL. The JSON-escaped slashes closed and
  the rest declined with their resolver named, so what was left open is the class rather than a
  list.
- 2026-08-11: The index counted four guardrail remainders, this one among them.
- 2026-08-16: Closed (ADR-0058 decision 9) on the candidate its own class owed: the tab at zero
  measured false positives and the line break declined at 42 extended spans.
