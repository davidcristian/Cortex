# The lookalike policy as the shipped default

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** a deployment measurement of how often a real turn names an internationalized host after
reading untrusted content. Two readings say cheaply whether anything has moved. The shipped default
is one binding, so
`grep -n output_guardrail brain/packages/orchestrator/src/cortex_orchestrator/config.py` reports
whether it is still `redact`. The corpus arm is the count of distinct non-ASCII hosts `URL_RE` finds
across every tracked file, each read as
`host_of(normalize_url(match.group(), confusables=False))`, which is the expression
`_UrlRedactingFilter._flagged` spends on the lookalike ground; it stood at 12 on 2026-09-08. The
body records what both answered when they were last taken.

The pass that added the third `OutputGuardrail` policy shipped the answer without imposing it:
`CORTEX_OUTPUT_GUARDRAIL` still defaults to `redact`, so the gap that pass closed is closed only
where someone opts in, and the shipped default still delivers a homoglyph host on a tainted turn.
That is deliberate rather than timid. The new ground costs a genuine internationalized domain named
on such a turn, and the decision to spend that belongs to a deployment rather than to the pass that
priced it.

What is missing is the one number that would settle it. The cost was measured against a domain
ranking, where 0 of the top 1,000 hosts and 1,441 of the top 1,000,000 are internationalized, and
against this repo's own corpus. Neither is the question. The question is how often **a real turn on
this machine** names such a host **after reading untrusted content**, which is a measurement of one
deployment's mail and files and not of the web, and nothing in the repo can stand in for it. A week
of turns with the policy on and the redactions counted answers it; so does a single user-visible
false positive, which is why this waits on being bitten rather than on being scheduled.

**Re-read 2026-09-08, and the corpus arm was six times out of date.** The default is unchanged:
`config.py` binds `output_guardrail` to `redact`, so the lookalike ground still ships off and the
paragraphs above still describe the code. The corpus is not what this entry recorded. `URL_RE` now
finds 2,997 matched spans across the 1,548 readable files of 1,574 tracked and 2,304,319 words,
reducing to 1,192 distinct identities, and the hosts among them that are not plain ASCII number
**12** where this entry claimed 2. Every one of the twelve is still a fixture, and they sit in four
files: this ADR, `brain/packages/core/tests/test_guardrail.py`, `docs/modules/brain-core.md`, and
[R-058](058-uts39-confusables-set.md). Three of the twelve are not hosts anybody wrote at all but
artifacts of the matcher running over Markdown, a backtick or an arrow being an ordinary body
character to it, so a homoglyph example inside a code span is read with its closing backtick and one
is read with the arrow after it. That sixfold growth is
itself the argument for leaving this open: the count rises with every addendum that writes a
homoglyph example down, so the corpus measures how much this ADR has been documented and not how
often a turn names such a host.

The change itself is one word in `config.py` plus the addendum that argues it, so nothing here is
blocked on design. What the entry holds is the evidence, and the standing trade this ADR was founded
on says which way to lean once the evidence exists: a missing link degrades a reply, and a delivered
phishing link harms the user.

## Trail

- 2026-09-08: **Not fired**, and the corpus figures in the body are repaired from a fresh reading.
  The trigger needs a measurement of this deployment's own turns and no such measurement has been
  taken, which the shipped default confirms from the other side: `output_guardrail` is still
  `redact`, so no turn has ever run under the lookalike ground here and there is nothing to count.
  The corpus arm was re-run over `git ls-files` at `HEAD` rather than trusted: 2,997 spans, 1,192
  distinct identities, 12 distinct non-ASCII hosts, all fixtures. Recorded in the twenty-first
  ADR-0015 addendum with the reading behind [R-294](294-one-match-yields-one-identity.md).
- 2026-08-16: Opened by the fourteenth ADR-0015 addendum on closing
  [R-283](283-a-chosen-homoglyph-outlives-any-table.md), which landed the lookalike policy as an
  opt-in and recorded the default question as the residue rather than answering it from a corpus
  that cannot see this deployment's turns.
