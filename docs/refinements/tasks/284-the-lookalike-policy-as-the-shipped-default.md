# The lookalike policy as the shipped default

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** a deployment measurement of how often a real turn names an internationalized host

The pass that added the third `OutputGuardrail` policy shipped the answer without imposing it:
`CORTEX_OUTPUT_GUARDRAIL` still defaults to `redact`, so the gap that pass closed is closed only
where someone opts in, and the shipped default still delivers a homoglyph host on a tainted turn.
That is deliberate rather than timid. The new ground costs a genuine internationalized domain named
on such a turn, and the decision to spend that belongs to a deployment rather than to the pass that
priced it.

What is missing is the one number that would settle it. The cost was measured against a domain
ranking, where 0 of the top 1,000 hosts and 1,441 of the top 1,000,000 are internationalized, and
against this repo's own corpus, where 1,413 URLs across every tracked file carry 2 distinct
non-ASCII hosts and both are fixtures. Neither is the question. The question is how often **a real
turn on this machine** names such a host **after reading untrusted content**, which is a
measurement of one deployment's mail and files and not of the web, and nothing in the repo can
stand in for it. A week of turns with the policy on and the redactions counted answers it; so does
a single user-visible false positive, which is why this waits on being bitten rather than on being
scheduled.

The change itself is one word in `config.py` plus the addendum that argues it, so nothing here is
blocked on design. What the entry holds is the evidence, and the standing trade this ADR was founded
on says which way to lean once the evidence exists: a missing link degrades a reply, and a delivered
phishing link harms the user.

## Trail

- 2026-08-16: Opened by the fourteenth ADR-0015 addendum on closing
  [R-283](283-a-chosen-homoglyph-outlives-any-table.md), which landed the lookalike policy as an
  opt-in and recorded the default question as the residue rather than answering it from a corpus
  that cannot see this deployment's turns.
