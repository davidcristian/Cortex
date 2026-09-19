# A chosen homoglyph outlives any table

**Status:** done 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

Opened by the pass that declined the full UTS-39 confusables set, as what that measurement found
rather than the work it declined. The deferral assumed a bigger table was the fix, and the
measurement says no table is, because the attacker picks the codepoint. Driven end to end through a
real `TaintLedger` and a real streaming filter, with a legitimate `http://example.com/invoice`
collected and the reply writing a lookalike of it, a homoglyph in the curated table is redacted by
both policies, while one outside it (U+0406 Cyrillic Byelorussian-Ukrainian I, among 635 the table
does not have) is delivered under the default policy and redacted under strict. `URL_RE` matches a
homoglyph host whatever the identity folds to, so the class is covered by the policy that does not
consult the identity, and by nothing else.

The default policy is what ships (`CORTEX_OUTPUT_GUARDRAIL=redact`), so this named a real
deployment gap: on a tainted turn, a reply containing a host that is a non-ASCII lookalike of a
link the turn legitimately read is delivered. The number to argue against is the one the
confusables decline published: stdlib NFKC already folds 52% of everything UTS-39 aims at an ASCII
host, the curated table covers 29 more, and the residue is 483 distinct characters after NFKC, of
which this interpreter's own character database cannot name 41.

## History

- 2026-08-16: Opened by the confusables costing (ADR-0058 decision 16), which declined the full
  confusables set and found that the defence against a chosen homoglyph is the policy rather than
  the fold.
- 2026-08-16: Done (ADR-0015 decision 8), and the narrower of the two answers won.
  `CORTEX_OUTPUT_GUARDRAIL=lookalike` is a third `OutputGuardrail` policy: the default one plus a
  rule that redacts a URL whose host is not plain ASCII on a tainted turn, whatever was collected.
  Strict did not become the default and the curated table did not grow. The port needed no change:
  `open(taint, *, allow)`, `TaintView` and `TaintLedger` are untouched, and what moved is behind
  the port, a policy becoming the set of rules it applies rather than a boolean. One subtlety the
  entry did not name: the host is read with the confusable fold switched off, since a host written
  wholly out of table entries folds to plain ASCII, and a rule reading the ordinary identity would
  have had a table-shaped hole exactly where the table is. Measured: 605 of 605 untabled UTS-39
  host-aimed characters redacted and 29 of 29 tabled ones, against 0 of the Tranco top 1,000
  legitimate hosts, 8 of the top 10,000 and 1,441 of 1,000,000. Validated live on the shipped
  cortex, where an ordinary user request to strip tracking parameters was enough to make the
  default policy deliver a homoglyph host that the new one redacts. Whether that policy should
  become the shipped default is
  [R-284](284-the-lookalike-policy-as-the-shipped-default.md).
