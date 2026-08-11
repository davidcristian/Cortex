# Mixed and other encodings past percent and HTML

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** unrecorded

It was recorded inside the model-independent output guardrail entry, in its list of what remains
behind the same seam (ADR-0015 deferred). The fragment, verbatim: mixed/other encodings past
percent + HTML.

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
