# Mixed and other encodings past percent and HTML

**Status:** landed 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

It was recorded inside the model-independent output guardrail entry, in its list of what remains
behind the same seam (ADR-0015 deferred). The fragment, verbatim: mixed/other encodings past
percent + HTML.

**Its two halves answered differently, and pricing them apart is what closed it.** *Mixed* is
already free and the measurement says how free: no position in this grammar was ever a list of
whole separators, each being an alternation generated per character, so every combination of the
colon's 9 spellings and the solidus's 17 across both authority slashes, 2,601 in all, folds to the
one identity. The 306 that decline do so correctly, a semicolon-less hexadecimal reference in front
of a host whose first letter is a hex digit (`&#x2Fevil`) being one three-digit reference and not a
solidus, which is the ninth addendum's own rule holding rather than a miss. So the half that reads
like the work was never owed anything, and that is a property of generating tables instead of
listing them.

*Other encodings* owed the resolver question one candidate, and the candidate that answers yes is
not an encoding of a character at all but the **absence** of one: a URL parser removes every ASCII
tab and newline from its input before it parses anything, at every position, so
`http://evil.exa<TAB>mple/pay` is the plain link to every conforming parser, the browser the user
pastes into included, and the overlay's `white-space: pre-wrap` bubble hands the character to the
clipboard intact. **The tab closed and the line break declined, on one measurement over the repo's
own prose**: 1,054 files, 1,348,844 words, 1,469 spans, with the tab adding, losing and extending
nothing at all, and the newline extending 42 spans by swallowing a line's end and the next line's
first word. That decline was already argued when the split host's space table left the
line-breaking family out, so this pass only put a number to it. The pass also fixed the one
ordering decision the fold makes: a tab between two labels keeps the **gap** reading (`evil.com`,
the reader's) rather than the parser's (`evildotcom`), because the whole defang family rests on the
reader, so the removal runs after the gap fold and the host classes keep excluding the character
that the body now admits. Eleven tests, each mutation-proven with `__pycache__` cleared and each
mutation verified applied, and the streaming needed no hold-back branch of its own, verified at
every two-way split point of nine probes under all three policies (1,299 splits). **This close
moves the area's count by one**, and it leaves one entry behind:
[R-285](285-a-tab-inside-a-scheme-word.md), the same character inside the scheme word or its
separator, which anchors nothing at all today.

## Trail

- 2026-08-08: Pricing this tail against the shipped module found source-code escapes
  (`evil\u002eexample`, `\x2e`, `\056`, `%u002e`, `\.`) folding to nothing, and JSON-escaped
  slashes, a whole percent-encoded scheme and a bracket-less entity colon (`https&#58;//…`)
  anchoring nothing; the same run turned up two bypasses that were not in this tail and landed
  them, and the tail stayed open.
- 2026-08-08: The bracket-less entity colon came off that table the same day, closed as a whole
  family generated per character from its codepoint, on the layer distinction that a renderer
  resolves an HTML reference before anything looks for a URL. The tail stayed open, one row
  shorter.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. It named the guardrail tails as live-observation shaped, the trigger being a
  deployment doing something rather than a file saying something, so no reading of the code
  settles it.
- 2026-08-10: The leftover table was priced whole by asking of each row whether a resolver in
  this system's path turns the spelling back into the attacker's URL. The JSON-escaped slashes
  closed and the rest declined with their resolver named, so the tail is open on its class
  rather than on a list, and its next reader owes it a candidate encoding put to that question
  rather than a row picked off a table.
- 2026-08-11: The index's fix-when-it-bites bucket counts four guardrail tails, this one among
  them, where five stood the day before and the fifth was the slashless authority URL.
- 2026-08-16: Closed as the fifteenth ADR-0015 addendum, on the candidate its own class owed
  rather than on the unrecorded trigger it had carried: the tab landed at zero measured false
  positives and the line break declined at 42 extended spans.
