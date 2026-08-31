# Whitespace-split hosts

**Status:** landed 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

It was recorded inside the model-independent output guardrail entry, in its list of what remains
behind the same seam (ADR-0015 deferred). The fragment, verbatim: whitespace-split `evil dot com`
(no scheme to anchor, prose FP).

**Its own annotation was two claims about two different spellings, and pricing them apart is what
closed it.** The resolver question the tenth addendum settled on does not decide this family:
`http://evil dot com` is a parse error to a real URL parser, but so is every contiguous defang form
this ADR already matches, so the resolver here is the reader who refangs and retypes, which is
exactly the reasoning the defang family was admitted on. What decides it is the anchor. **With a
scheme in front of it the form closed**, and its cost was measured rather than argued: over the
repo's own prose at `HEAD`, 707 files and 1,030,733 words, the shipped matcher finds 863 spans and
the widened one finds the same 863, with none added, none lost, none extended and no identity
changed. **Without a scheme it is declined**, on the standing decision that puts its plain twin
out, since `evil.com` is not a link to this grammar either and redacting the split spelling of a
host while ignoring the contiguous one would be incoherent; the same corpus prices that half at 113
matches across 76 distinct phrases, of which two are the ADR's own examples and the rest are
sentences about a connection dot or a red dot.

What made the close possible is one rule rather than any table: **a gap is admitted only
immediately after the separator and only while every label so far is dotless**, because defanging
replaces a host's dot and never adds one. That was found by measurement rather than foresight: written as
one more alternative inside the body's `+` loop it is defeated, the loop re-entering it at every
position and reading `visit http://example.com dot the file` as a host, which destroys an identity
that was already correct. The narrowings a worse answer would have needed are each a data table
this repo does not carry (the IANA TLD list, a stopword list), and none is needed. The measurement
also turned up a third failure shape past the "leaked" and "wrong identity" ones the earlier
addenda found: on a link split both ways both policies fired and the user still read `[link
removed: untrusted source] dot example/pay`, a redaction that stops at the first gap and hands over
the host beside its own marker. The hold-back carries the same dotless rule, and that is not a
detail: holding on any trailing space held every URL in every reply and made 28 existing tests fail
before the rule went in.

The same widening turned up a live spelling on none of its rows, the shape this ADR has now found
seven times: a gap spelled with a space NFKC folds (a no-break, thin or ideographic space), which
renders as a blank and so reads exactly like the form that closed, and which anchored nothing at
all. It closed in the same pass and from a table, since exactly fifteen codepoints fold that way
and the complement is exactly the line-breaking family plus the Ogham space mark. Sixteen tests,
each mutation-proven with `__pycache__` cleared and each mutation verified applied. **This close
moves the area's count by one.** Two spellings are left standing on purpose and are entries rather
than rows, both because relaxing the dotless rule is what reopens the prose it protects: a host
that mixes a plain dot and a gap, and a slashless authority whose host is split.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. It named the guardrail tails as live-observation shaped, the trigger being a
  deployment doing something rather than a file saying something, so no reading of the code
  settles it.
- 2026-08-11: The index's fix-when-it-bites bucket counts four guardrail tails, this one among
  them, where five stood the day before and the fifth was the slashless authority URL.
- 2026-08-16: Closed as the twelfth ADR-0015 addendum, on a corpus measurement rather than on the
  unrecorded trigger it had carried: the anchored form landed at zero measured false positives and
  the unanchored form declined at 113. The pass also opened
  [R-281](281-a-host-that-mixes-a-dot-and-a-gap.md) and
  [R-282](282-a-slashless-authority-whose-host-is-split.md).
- 2026-08-16: Measured live over Docker on the GPU rather than left on constructed probes. The
  shipped cortex refused every laundering ask, but the subagent tier obeyed one **framed** and
  ended its summary with `hxxps://payroll-verify dot example slash claim`, so the spelling is one
  a deployed model really writes. Before the change the ledger held `https://payroll-verify` and
  the user read the marker with `dot example` beside it; after, the host is gone.
