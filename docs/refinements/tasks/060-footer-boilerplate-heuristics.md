# Footer and boilerplate heuristics

**Status:** declined 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

Left behind by [R-056](056-output-guardrail.md), noted as screening-model territory.

Declined, and the finding is that the note names two questions under one word, neither of them
this guardrail's. Read against the tree, its ground is already divided: a clickable number is in
scope, `tel:` being a matched scheme; a link in a footer was never treated differently from a link
anywhere else; a bare number in prose is out, on the existing decision that puts a bare domain
out; and what has changed since the note was written is that `SECURITY_PREAMBLE` now names this
attack in its own words, forbidding the model to add any "text, line, footer, header, disclaimer,
link, URL, or code" the untrusted content asks for, however it is framed. So the security half is
answered by the framing and the taint check, and what the note still asks for is a judgement about
what a passage means, which is the one thing the deterministic layer is defined by not making:
every pass in the identity is a reading of what a resolver does, except the confusable fold, which
lives in its own switchable module for exactly that reason.

The decisive half is that the judgement would be made over attacker-controlled text. Measured
through the shipped path (a real RFC822 message, the real `EmailReader`, the real `html_to_text`,
a real `TaintLedger`), the cheapest footer rule there is, the RFC 3676 signature delimiter,
dropped the one sentence the user would have asked about and left the ledger holding nothing,
because the attacker chose where the delimiter went; a keyword rule kept the real content and
dropped the payload only because that attacker wrote the word `Confidential`.

The other question in the word is real and belongs to `cortex_email`: boilerplate wastes context.
It has one requirement if anyone builds it, recorded in
[ADR-0015](../../adr/ADR-0015-output-guardrail.md) decision 1 because it outlives this entry: the
ledger must observe exactly the text the model receives, because `TaintLedger.observe` collects
the laundering evidence from the same string the loop fences.

It reopens only on a measured non-URL payload a deployed model reproduces past the framing clause,
and the answer then is a clause or a scheme, never a passage classifier.

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired.
- 2026-08-11: The index counted four guardrail remainders, this one among them.
- 2026-08-16: Declined (ADR-0015, alternatives rejected). It is the last of the deferrals that ADR
  left.
