# Pricing the leftover obfuscation table

**Status:** landed 2026-08-10
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

This pass closed one row and declined the rest with the
reason written down, and the tail they sit in stays open on its class. The pass decided every row by
one question, asked of the shipped path rather than of the spelling: **is there a resolver in
this system's path for untrusted content that turns this spelling back into the attacker's
URL?** Tracing where guardrail output goes answered half of it and corrected the picture the
earlier entries carried. Nothing downstream of the filter resolves anything: the scrubbed text is
folded into `TextDelta` (`engine.py`), mapped to the wire (`converse_stream.py`), turned into a
delta by the body (`body/crates/rpc/src/converse.rs`), appended by the reducer
(`overlay/turnState.ts`) and rendered as a React **text child** (`WhisperBubble.tsx`,
`Message.tsx`), with no Markdown renderer, no HTML sink, no linkifier and no clipboard path in
the overlay's three runtime dependencies. **The overlay never makes any URL clickable**, so
"clickable" was never the criterion here: the resolver that matters on the reply side is the
browser the user pastes into, and that was run (`node`, which implements the same WHATWG URL
parsing every browser does) rather than reasoned about. **One row is live and it closed.** `https:\/\/evil.example/pay`
is not a rendering of the link, it is the link: the URL Standard skips `/` and `\` alike in a
special scheme's authority and converts a path backslash to a solidus, so `new URL` returns the
plain link for the JSON-escaped spelling, for `https:\\…`, for `https:/\…` and for a path
backslash. The first three anchored **nothing**, so neither policy matched them (the severe
shape a fourth time), and the fourth carried a second identity the collected set never held, the
CJK-dot shape. Both directions were measured through a real `TaintLedger` and a real streaming
filter fed one character at a time, and the collected side is the worse one: untrusted content
that writes its link JSON-escaped put nothing in the ledger, so the *plain* link in the reply was
not redacted either. The fix is the eighth addendum's shape, grammar and identity only, no seam
change: the backslash joins the solidus table so every mixture is generated, `_spellings` now
generates entity references for every glyph HTML names (so `&#92;`/`&bsol;` join `&#47;`/`&sol;`,
1125 generated combinations all folding), and `_fold_special_slashes` gives the identity the
parser's own rule, scoped to the schemes it holds for, so `mailto:a\b@x` keeps its backslash.
**Each decline names its resolver and its absence.** A source-code escape is resolved
by a compiler that is not here, and the parser that *is* here reads the escaped host
`evil\u002eexample` as the host `evil` with the rest in the path. The identity now says that too,
so folding the backslash did not admit these rows, it sharpened the decline. `%u002e` is not a
percent-escape at all and the parser rejects the URL outright. A bracketless percent-encoded
separator is resolved by nobody, now confirmed: `new URL` throws. Stacked
references still need two passes, and the one place a second pass exists already composes to a
catch, measured rather than assumed: an HTML email spelling `https&amp;#58;//…` reaches the ledger
as `https&#58;//…` because the sidecar's `html_to_text` is the first pass, and the shipped grammar
anchors that. The one resolver that would reopen a declined row is a **Markdown renderer**
(CommonMark backslash-escapes any ASCII punctuation, so `evil\.example` would render live), and
there is none in this repo; that is the trigger, and it reopens the row as a family rather than as
a spelling. The accepted cost is a JavaScript regex literal (`/^https:\/\/example\.com/`), which
strict mode on a tainted turn now redacts as it already redacted the same snippet written plainly;
the default policy still replaces only what the ledger collected. Eleven tests, each
mutation-proven with `__pycache__` cleared and each mutation verified applied, plus every two-way
split point of six probes under both policies. **The pricing itself moves no count**, on the
convention the two entries above set rather than by copying it: what closed was a row in a table,
never counted as an entry, and the counted tail it belongs to, "mixed/other encodings past
percent + HTML", is still open. The area's count does move, by one, and the entry below is the
reason and says so. What it is open *on* has changed, and that is the honest residue of this pass: every
spelling its table carried is now priced, so the tail is open on the class and not on a list, and
its next reader owes it a candidate encoding put to the question above rather than a row picked
off a table.

## Trail

- 2026-08-10: Landed as the tenth ADR-0015 addendum. One row closed, the JSON-escaped slashes,
  and every other row declined with its resolver and that resolver's absence named; the pricing
  itself moved no count.
- 2026-08-10: The same run found a live spelling on none of the table's rows and opened it as an
  entry rather than chasing it, which is the one thing in the pass that moved the area's count.
