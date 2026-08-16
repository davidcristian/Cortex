# A chosen homoglyph outlives any table

**Status:** open, a seam or port change comes first
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

Opened by the pass that declined the full UTS-39 confusables set, and it is the residue that pass
found rather than the work it declined. The two are opposites: the deferral assumed a bigger table
was the fix, and the measurement says **no table is**, because the attacker picks the codepoint.
Driven end to end through a real `TaintLedger` and a real streaming filter, with a legitimate
`http://example.com/invoice` collected and the reply spelling a lookalike of it, a homoglyph in the
curated table is redacted by both policies while one outside it (U+0406 Cyrillic Byelorussian-
Ukrainian I, among 635 the table does not carry) **leaks under the default policy and is redacted
under strict**. `URL_RE` matches a homoglyph host whatever the identity folds, so the class is
covered identity-independently by the policy that does not consult the identity, and by nothing
else.

The default policy is what ships (`CORTEX_OUTPUT_GUARDRAIL=redact`), so this names a real
deployment gap and not a hypothetical: on a tainted turn, a reply carrying a host that is a
non-ASCII lookalike of a link the turn legitimately read is delivered. The obvious answers each
need a decision this backlog is the right place to hold rather than an addendum. Making strict the
default trades a known over-redaction across every tainted turn for it. Narrower, and more
interesting: the default policy could redact a URL whose host carries a character **outside** the
identity's ASCII result even when that identity was not collected, which is a rule about the shape
of what is emitted rather than about matching a collected string, and so is a third policy rather
than a widening of either. That is a seam-shaped change: `OutputGuardrail` has carried exactly two
policies since it landed, and a third is where the shape of the port gets tested.

The number to argue against is the one the declining addendum published: stdlib NFKC already folds
52% of everything UTS-39 aims at an ASCII host, the curated table covers 29 more, and the residue
is 483 distinct characters after NFKC, of which this interpreter's own character database cannot
name 41.

## Trail

- 2026-08-16: Opened by the thirteenth ADR-0015 addendum, which declined the full confusables set
  and found that the boundary against a chosen homoglyph is the policy rather than the fold. Filed
  as a seam-shaped entry because the fix it points at is a third `OutputGuardrail` policy.
