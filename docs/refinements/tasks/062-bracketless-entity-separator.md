# Bracketless HTML character reference separator

**Status:** landed 2026-08-08
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

This is the leftover the entry above
named as its natural next pass, and the tail it came out of still stays open. Measured the same
way first, through a real `TaintLedger` holding a collected `https://evil.example/pay` and a real
streaming filter fed one character at a time: `https&#58;//evil.example/pay` anchored **no match
at all**, so both policies were blind to it, the severe shape a third time. Fixing the one
measured spelling would have left ten, because the reference is a family: the decimal and
hexadecimal forms, zero-padded (`&#0058;`, `&#x003a;`) or not, with HTML's optional semicolon or
without, upper or lower case, the named `&colon;` and `&sol;`, and the solidi as well as the
colon, every one of them live and every one now generated from the character's codepoint
(`_entity_forms`) so a spelling nobody thought of is not the one that gets through. Mixtures with
the fullwidth glyphs come free, since the matcher composes the per-character alternations.
**The renderer is what puts this on the closed side of the line the entry above drew**, re-weighed
rather than inherited: an HTML character reference is a *text-layer* encoding a renderer resolves
before anything looks for a URL, so an HTML email body reading `https&#58;//evil.example` displays
and autolinks the plain link and the reader decodes nothing, while a source-code escape is
resolved by a compiler that is not in the picture and a *bracketless* percent-escape is resolved
by nobody, since percent-decoding only ever runs inside a string already recognized as a URL. The
same "one rendering pass" rule keeps `&COLON;` (HTML's named references are case-sensitive, so
the anchor scopes that alternative back with `(?-i:…)`), `&#58123` (one five-digit reference, so
the semicolon-less forms carry a digit-run guard) and `&amp;#58;` (renders as *text*) out, which
is what keeps the anchor's promise that every spelling it admits is one the identity folds.
`url_identity.py` did not change at all: the decode fixpoint already folded all of this and the
whole gap was that nothing reached it. The streaming hold-back grew the second branch it needed
(`_OPEN_SEP_RE`, a scheme word then complete separator spellings then an unfinished reference,
the leading `&` load bearing so `database` is not held), verified at all 840 two-way split points
of the measurement's probes. Eleven tests, each mutation-proven with `__pycache__` cleared and
each mutation verified applied; the first fixture written for the digit-run guard did not redden
it and was replaced with one that does. **The count does not move**, on the same reasoning as the
entry above rather than by copying its answer: what closed here was never counted (it was named
in that entry's leftover table, not carried as an item, the treatment the bracket asymmetry got),
and the counted tail it belongs to, "mixed/other encodings past percent + HTML", is still open,
now one row shorter and with its argument sharpened from a different measurement to a different
layer. What stays deferred there: source-code escapes (`evil\u002eexample`, `\x2e`, `\056`,
`%u002e`, `\.`, `https:\/\/…`), a bracketless percent-encoded separator or whole scheme
(`https%3A//…`, `https%3A%2F%2F…`), and stacked references (`&amp;#58;`).

## Trail

- 2026-08-08: Landed as the ninth ADR-0015 addendum, the leftover the eighth had named as its
  natural next pass. The count did not move, since what closed was a row in a leftover table
  rather than an entry anyone had counted.
