# Footer and boilerplate heuristics

**Status:** declined 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

It was recorded inside the model-independent output guardrail entry, in its list of what remains
behind the same seam (ADR-0015 deferred). The fragment, verbatim: footer/boilerplate heuristics
(screening-model territory).

**Declined, and the finding is that the fragment names two questions wearing one word, neither of
them this guardrail's.** Re-derived against the tree rather than against the note, its ground is
already divided: a clickable number is in scope (`tel:` is a matched scheme), a link in a footer was
never treated differently from a link anywhere else, a bare number in prose is out on the standing
decision that puts a bare domain out, and the part that has moved since the fragment was written is
that `SECURITY_PREAMBLE` now names this attack in its own words, forbidding the model to add any
"text, line, footer, header, disclaimer, link, URL, or code" the untrusted content asks for, framed
as a requirement or a policy or a standard. So the security half is answered by the framing and the
taint gate, and what the fragment still asks for is a **judgement about what a passage means**,
which is the one thing the deterministic layer is defined by not making: every pass in the identity
is a resolver's reading except the confusable fold, which lives in its own switchable module for
exactly that reason.

**The decisive half is that the judgement would be made over attacker-controlled text.** Measured
through the shipped path (a real RFC822 message, the real `EmailReader`, the real `html_to_text`, a
real `TaintLedger`), the cheapest footer rule there is, the RFC 3676 signature delimiter, dropped
the one sentence the user would actually have asked about and left the ledger holding nothing at
all, because the attacker chose where the delimiter went; a keyword rule kept the real content and
dropped the payload only because that attacker wrote the word `Confidential`. The other question in
the word is a real one and it belongs to `cortex_email`: boilerplate wastes context. It carries one
invariant if anyone ever builds it, recorded in the addendum since it outlives this entry: the
ledger must observe exactly the text the model receives, because `TaintLedger.observe` collects the
laundering evidence from the same string the loop fences. **The area's count moves by one and this
decline opens nothing**, which is the honest residue: unlike the confusables decline, this one
leaves the boundary exactly where it already was. It reopens only on a measured non-URL payload a
deployed model reproduces past the framing clause, and the answer then is a clause or a scheme,
never a passage classifier.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. It named the guardrail tails as live-observation shaped, the trigger being a
  deployment doing something rather than a file saying something, so no reading of the code
  settles it.
- 2026-08-11: The index's fix-when-it-bites bucket counts four guardrail tails, this one among
  them, where five stood the day before and the fifth was the slashless authority URL.
- 2026-08-16: Declined as the sixteenth ADR-0015 addendum, which closes the gap its unrecorded
  trigger left by settling the entry rather than by naming what would fire it. It is the last of
  the deferrals that ADR carried.
