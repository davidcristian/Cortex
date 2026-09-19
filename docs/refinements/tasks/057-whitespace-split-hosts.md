# Whitespace-split hosts

**Status:** done 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

Left behind by [R-056](056-output-guardrail.md): a host written with gaps, `evil dot com`, with no
scheme to anchor on and a risk of matching ordinary prose.

The note was two claims about two different forms, and pricing them apart is what closed it. With
a scheme in front of it the form closed, and its cost was measured rather than argued: over the
repo's own prose at `HEAD`, 707 files and 1,030,733 words, the shipped matcher finds 863 spans and
the widened one finds the same 863, with none added, none lost, none extended and no identity
changed. Without a scheme it is declined, on the existing decision that leaves its plain twin out:
`evil.com` is not a link to this grammar either, and removing the split form of a host while
ignoring the contiguous one would be inconsistent. The same corpus prices that half at 113 matches
across 76 distinct phrases, of which two are the ADR's own examples and the rest are sentences
about a connection dot or a red dot.

What made the close possible is one rule rather than a table: a gap is admitted only immediately
after the separator and only while every label so far has no dot, because defanging replaces a
host's dot and never adds one. That was found by measurement rather than foresight. Written as one
more alternative inside the body's `+` loop it fails, the loop re-entering it at every position and
reading `visit http://example.com dot the file` as a host, which destroys an identity that was
already correct. The narrower alternatives would each have needed a data table this repo does not
have, such as the IANA TLD list or a stopword list, and none is needed.

The measurement also turned up a third failure form past the leaked and wrong-identity ones found
earlier: on a link split both ways both policies fired and the user still read
`[link removed: untrusted source] dot example/pay`, a redaction that stops at the first gap and
hands over the host beside its own marker. The streaming hold-back uses the same no-dot rule,
which matters: holding on any trailing space held every URL in every reply and made 28 existing
tests fail before the rule went in.

The same widening turned up a live form on none of its rows: a gap written with a space that NFKC
folds, such as a no-break, thin or ideographic space, which renders as a blank and so reads
exactly like the form that closed, and which anchored nothing. It closed in the same pass and from
a table, since exactly fifteen codepoints fold that way and the rest are the line-breaking family
plus the Ogham space mark. Sixteen tests, each reverted with `__pycache__` cleared and each
reversion verified applied.

Two forms are deliberately left open as their own entries, because relaxing the no-dot rule is what
reopens the prose it protects: [R-281](281-a-host-that-mixes-a-dot-and-a-gap.md) and
[R-282](282-a-slashless-authority-whose-host-is-split.md).

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired.
- 2026-08-11: The index counted four guardrail remainders, this one among them.
- 2026-08-16: Closed (ADR-0058 decision 8) on a corpus measurement rather than on a trigger: the
  anchored form at zero measured false positives, the unanchored form declined at 113. The pass
  opened [R-281](281-a-host-that-mixes-a-dot-and-a-gap.md) and
  [R-282](282-a-slashless-authority-whose-host-is-split.md).
- 2026-08-16: Measured live over Docker on the GPU rather than on constructed probes. The shipped
  cortex refused every laundering request, but the subagent tier obeyed one even when framed and
  ended its summary with `hxxps://payroll-verify dot example slash claim`, so this is a form a
  deployed model really writes. Before the change the ledger held `https://payroll-verify` and the
  user read the marker with `dot example` beside it; after it, the host is gone.
