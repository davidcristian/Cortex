# Model-independent output guardrail

**Status:** done 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

The defence against laundering a link through the model, which does not depend on the prompt. The
`TaintLedger` collects every URL untrusted content brings into the turn, and the engine's
`UrlRedactingGuardrail`, an `OutputGuardrail` port in `TurnCapabilities`, removes any of them that
reappear in the reply, minus the user's own, before the user sees it. It works while streaming,
and the stored reply equals the shown reply. On by default
(`CORTEX_OUTPUT_GUARDRAIL=redact`, `off` disables it).

Strict mode followed on 2026-07-06: `CORTEX_OUTPUT_GUARDRAIL=strict`
(`StrictUrlRedactingGuardrail`) removes every non-user URL on a tainted turn, which does not
depend on the link being written the same way twice and so answers a transformed or reconstructed
link. That required the port to expose the live `TaintView`, the taint bit and the URLs, rather
than the URL subset alone.

Everything after that widened the URL grammar and the identity it folds to, with no port change,
so both policies inherit each addition. In order: `mailto:` coverage; contiguous defang forms
(`hxxp://`, `evil[.]com`, `evil[dot]com`, `[://]` separators); percent-decoding and NFKC folding,
plus the `ftp://` and `tel:` schemes, anchored on word boundaries so `sftp://` and `hotel:` do not
partially match; percent-decoding to a bounded fixpoint and a curated cross-script confusable
table; HTML character references and the `data:` scheme behind a MIME-type lookahead; the
encoded-inner defang dot, which widened the matcher's bracket token to a whole bracket chunk; and
finally the encoded defang separator, a bracket-shape asymmetry found while fixing it, punycode
decoding of `xn--` labels through the stdlib `idna` module, and Cf-category format characters
(zero-width space and joiner, soft hyphen, BOM) stripped after decoding. Each fix was reverted
individually to check that its tests fail. `urls.py` hit the 300-line cap and split, keeping the
grammar while `url_identity.py` took the identity passes, with `extract_urls` staying put so only
`guardrail.py`'s import moved.

Five things were left behind it: whitespace-split hosts
([R-057](057-whitespace-split-hosts.md)), the full UTS-39 confusables set
([R-058](058-uts39-confusables-set.md)), mixed and other encodings past percent and HTML
([R-059](059-mixed-other-encodings.md)), footer and boilerplate heuristics
([R-060](060-footer-boilerplate-heuristics.md)), and a structured redaction event for the overlay
([R-065](065-structured-redaction-event.md)).

## History

- 2026-07-03: The guardrail shipped, with the `TaintLedger` collecting untrusted URLs and the
  `UrlRedactingGuardrail` removing them behind the `OutputGuardrail` port.
- 2026-07-06: Strict mode and `mailto:` coverage, then the defang forms, then percent-decoding,
  NFKC folding and the `ftp://` and `tel:` schemes.
- 2026-07-08: Percent-decoding became a bounded fixpoint and a curated cross-script confusable
  table was added, both grammar and identity only.
- 2026-07-13: HTML character references and the `data:` scheme, then the encoded-inner defang dot,
  then the encoded defang separator, punycode and zero-width format characters, which split
  `urls.py` into the grammar and `url_identity.py` into the identity passes.
