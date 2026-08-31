# Model-independent output guardrail

**Status:** landed 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

The prompt-independent laundering defense the hardening addendum deferred: the `TaintLedger`
collects every URL untrusted content carries into the turn, and the engine's
`UrlRedactingGuardrail` (an `OutputGuardrail` seam in `TurnCapabilities`) redacts any that
reappear in the reply (minus the user's own) before the user sees it, streaming-safe;
the persisted reply equals the shown reply. On by default (`CORTEX_OUTPUT_GUARDRAIL=redact`,
`off` disables). **Strict mode + `mailto:` coverage landed 2026-07-06
([ADR-0015 addendum](../../adr/ADR-0015-output-guardrail.md)):** `CORTEX_OUTPUT_GUARDRAIL=strict`
(`StrictUrlRedactingGuardrail`) redacts *every* non-user URL on a tainted turn. It is verbatim-
independent, the answer to a transformed/reconstructed link. That required the seam to open
over the live `TaintView` (taint bit + URLs) rather than the URL subset alone; and
`extract_urls`/`_URL_RE` now cover `mailto:` (a real exfil vector) in both modes. **The
defanging subclass of obfuscation-resistant matching landed 2026-07-06 ([ADR-0015 second
addendum](../../adr/ADR-0015-output-guardrail.md)):** the shared URL grammar (`_URL_RE` + a `_refang`
pass in `_normalize`) now recognizes contiguous defang forms (`hxxp://`, `evil[.]com`,
`evil[dot]com`, `[://]`/`[:]//` separators) and refangs them to one canonical identity, so a
defanged link that formerly slipped past *both* redact and strict mode is caught on both the
collection and reply sides, with no seam change (grammar-only). **Three more obfuscation-resistant
classes landed 2026-07-06 ([ADR-0015 third addendum](../../adr/ADR-0015-output-guardrail.md)):**
the grammar split into `cortex_core/urls.py` (grammar + identity) from `guardrail.py` (redactor +
policies), and `normalize_url` gained **percent-decoding** (`evil%2ecom`→`evil.com`) + **NFKC**
folding (fullwidth/compatibility homoglyphs → ASCII), while the matcher gained the **`ftp://`
and `tel:`** schemes (word-boundary-anchored so `sftp://`/`hotel:` don't partial-match). Still
deterministic/stdlib, no seam change, redact + strict inherit it. **Two more obfuscation-resistant
classes landed 2026-07-08 ([ADR-0015 fourth addendum](../../adr/ADR-0015-output-guardrail.md)):**
`normalize_url` now **percent-decodes to a bounded fixpoint** (`evil%252ecom`→`evil.com`, closing
the multi-pass-encoding gap, reversing the third addendum's deliberate single-pass boundary, since
the decode is symmetric and so only *widens* a redaction) and folds a **curated cross-script
confusable table** (Cyrillic/Greek Latin-lookalikes → ASCII, e.g. Cyrillic `расе`→`pace`), the
dependency-free 95% of the homoglyph class, still grammar/identity-only, no seam change, redact +
strict inherit both, and the passes compose (a percent-encoded homoglyph decodes then folds).
**HTML-entity encoding + the `data:` scheme landed 2026-07-13 ([ADR-0015 fifth
addendum](../../adr/ADR-0015-output-guardrail.md)):** the percent-decode generalized to a combined
`_decode_escapes` fixpoint that also decodes **HTML character references** (`evil&#46;com`→`evil.com`,
the way HTML email, the chief untrusted source, renders a hidden dot), run **before** refang so an
entity-hidden defang bracket folds too; and `data:` became a matched scheme, admitted only behind a
**MIME-type lookahead** (`data:text/html;base64,…` matches, `data:the results` prose does not), a
proactive maintainer-sanctioned reversal like `mailto:`. Both stay grammar/identity-only (no seam change),
deterministic/stdlib (`html.unescape`), redact + strict inherit them. **The encoded-inner defang dot
landed 2026-07-13 ([ADR-0015 sixth addendum](../../adr/ADR-0015-output-guardrail.md)):** a defang dot whose
inner is encoded (`evil[&#46;]com`, `evil(%2e)com`, an entity-encoded `dot`) behind a *literal* closing
bracket used to escape both modes, because `_DEFANG_DOT` matched the raw text atomically and the raw
`]`/`)`/`}` (not a `_URL_CHAR`) ended the match before decode ran. The matcher's bracket token widened
from the literal `_DEFANG_DOT` to a bracket *chunk* (`_DEFANG_CHUNK`: opener + non-empty non-bracket run
+ closer) that consumes the whole `[...]` with its closer, so decode+refang fold it like the
entity-*bracket* case; the refanger keeps the literal `_DEFANG_DOT` (post-decode), so only a chunk that
decodes to a dot folds, any other stays verbatim. Unlike every earlier addendum this one **adds a
bounded new match surface** (a bracketed run in the body is now consumed whole, not cut at `]`), the
accepted tradeoff being symmetric/over-redaction-only: a bare `[]` still terminates, Markdown `(url)`
still bounds, the matcher stays linear, and the whole guardrail is `off`-able. **The encoded defang
separator, punycode, and zero-width format characters landed 2026-07-13 ([ADR-0015 seventh
addendum](../../adr/ADR-0015-output-guardrail.md)),** closing **four** live bypasses verified against the
shipped module first, two of which matched *nothing at all* and so escaped **both** redact and strict
mode. (1) The encoded separator (`http[&#58;//]evil.com`) is admitted as a bracket chunk whose inner
carries an **escape marker** (`&`/`%`), the decode fixpoint then resolving whichever encoding it was:
the sixth addendum's "needs enumeration or whole-stream decode, both rejected" was a **false
dichotomy**, since constraining the *shape* of an escape is a third option, and the marker is what keeps it
bounded (an unconstrained chunk matches prose like `http(s)-only`, which strict mode would redact out
of the repo's own docs). (2) A **bracket-shape asymmetry** found while widening that position: the
refanger always folded `(.)`/`{.}` but the separator tables listed only the square form, so
`http(://)evil.com` anchored nothing; every defang token now derives from one `_BRACKETS` table.
(3) **Punycode** decoding of `xn--` labels (stdlib `idna`, so the "needs a dependency" claim was
wrong for this half) feeds a registered IDN homoglyph to the existing confusable table. (4)
**Cf-category format characters** (zero-width space/joiner, soft hyphen, BOM) are stripped after
decoding; they render as nothing yet survive NFKC, and no prior addendum had named them. Each fix is
mutation-proven (reverting it individually makes the new tests fail); `urls.py` hit the 300-line cap
and split, keeping the **grammar** while `url_identity.py` took the **identity** passes, with
`extract_urls` staying put so only `guardrail.py`'s import moved. Remaining behind the same
seam (ADR-0015 deferred): whitespace-split
`evil dot com` (no scheme to anchor, prose FP); the **full UTS-39 confusables set**
(needs a dependency); mixed/other encodings past percent + HTML; footer/boilerplate heuristics
(screening-model territory); and a structured redaction event for the overlay (**not** a proto
change, as `StatusUpdate` and the overlay status chip already exist; its real cost is that
`OutputFilter.feed` returns `str`, so no redaction signal reaches the engine).

## Trail

- 2026-07-03: The guardrail landed as the prompt-independent laundering defense, with the
  `TaintLedger` collecting untrusted URLs and the `UrlRedactingGuardrail` redacting them behind
  the `OutputGuardrail` seam.
- 2026-07-06: Strict mode and `mailto:` coverage landed, then the defanging subclass of
  obfuscation-resistant matching, then three more classes (percent-decoding, NFKC folding, and
  the `ftp://` and `tel:` schemes).
- 2026-07-08: Percent-decoding went to a bounded fixpoint and a curated cross-script confusable
  table landed, both grammar and identity only.
- 2026-07-13: HTML character references and the `data:` scheme landed, then the encoded-inner
  defang dot, then the encoded defang separator, punycode and zero-width format characters,
  which split `urls.py` into the grammar and `url_identity.py` into the identity passes.
