# The lookalike policy as the shipped default

**Status:** open, waiting for its trigger
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** a deployment measurement of how often a real turn names an internationalized host
after reading untrusted content: the sum of `lookalike=` over the `cortex_core.turn_output` lines
`the output guardrail removed links from this reply` with `policy=lookalike`, across a week of
turns under that policy. Two readings say cheaply whether anything has moved. The shipped default
is one binding, so
`grep -n output_guardrail brain/packages/orchestrator/src/cortex_orchestrator/config.py` reports
whether it is still `redact`. The corpus reading is the count of distinct non-ASCII hosts `URL_RE`
finds across every tracked file, each read as
`host_of(normalize_url(match.group(), confusables=False))`, the expression
`_UrlRedactingFilter._flagged` uses for the lookalike rule; it stood at 12 on 2026-09-08,
2026-09-11 and 2026-09-17, and at 10 on 2026-09-24.
**Verified:** 2026-09-24

The pass that added the third `OutputGuardrail` policy shipped the answer without imposing it:
`CORTEX_OUTPUT_GUARDRAIL` still defaults to `redact`, so the gap that pass closed is closed only
where someone opts in, and the shipped default still delivers a homoglyph host on a tainted turn.
That is deliberate. The new rule costs a genuine internationalized domain named on such a turn, and
the decision to pay that belongs to a deployment.

What is missing is the one number that would settle it. The cost was measured against a domain
ranking, where 0 of the top 1,000 hosts and 1,441 of the top 1,000,000 are internationalized, and
against this repo's own corpus. Neither is the question. The question is how often a real turn on
this machine names such a host after reading untrusted content, which is a measurement of one
deployment's mail and files and not of the web. A week of turns with the policy on and the
redactions counted by rule would answer it. `REDACTED_LINK` is the same text whichever rule removed
the link, so the count is read off the line a settled reply logs when it lost one, which has a
count per rule and counts a link under the lookalike rule only when no other active rule took it
(ADR-0015 decision 9). A single user-visible false positive answers it too, which is why this waits
on a real problem rather than on a schedule.

The corpus count is not a stand-in for that measurement, and it has been wrong in this entry once
before: it claimed 2 where a fresh reading found 12. Every one is a fixture, and on 2026-09-24 the
ten sat in four files: this ADR, `brain/packages/core/tests/test_guardrail.py`,
`docs/readings/output-guardrail.md`, and [R-058](058-uts39-confusables-set.md). Some are not hosts
anybody wrote but artifacts of the matcher running over Markdown, such as a host read with its
closing backtick, since a backtick is an ordinary body character to it. The count rises with every
document that writes a homoglyph example down, so it measures how much this decision has been
documented rather than how often a turn names such a host.

The change itself is one word in `config.py` plus the decision record that argues it, so nothing is
blocked on design. What this entry waits for is the evidence, and the trade this decision was
founded on says which way to lean once it exists: a missing link degrades a reply, and a delivered
phishing link harms the user.

## History

- 2026-08-16: Opened when the lookalike policy was added as an opt-in
  ([R-283](283-a-chosen-homoglyph-outlives-any-table.md)), recording the default question rather
  than answering it from a corpus that cannot see this deployment's turns.
- 2026-09-08: Not triggered, and the corpus figures repaired from a fresh reading. `config.py`
  still binds `output_guardrail` to `redact`, so no turn has ever run under the lookalike rule here
  and there is nothing to count. The corpus reading over `git ls-files` at `HEAD`: 2,997 spans,
  1,192 distinct identities, 12 distinct non-ASCII hosts, all fixtures. Recorded in
  [docs/readings/output-guardrail.md](../../readings/output-guardrail.md).
- 2026-09-11: Not triggered, both readings taken again. The corpus: 1,589 tracked files, 1,563
  readable, 2,374,614 words, 3,007 matched spans reducing to 1,200 distinct identities, and 12
  distinct non-ASCII hosts, the same twelve in the same four files. The corpus grew by 15 tracked
  files and 10 spans and the count did not move, which is what the entry predicts.
- 2026-09-17: Not triggered, both readings taken again, and the measurement the trigger waits on
  was found to have no instrument. `config.py:146` binds `output_guardrail` to `"redact"`, and this
  checkout has no `.env`. No compose file passed `CORTEX_OUTPUT_GUARDRAIL` into the brain either,
  so the policy could not be switched on in the Docker stack; the same day the compose base file
  began passing it by name with the brain's other settings. The corpus: 1,663 tracked files, 1,637
  readable, 2,578,187 words, 3,018 spans reducing to 1,198 distinct identities, and 12 distinct
  non-ASCII hosts. The new finding was in the remedy: `guardrail.py` had no logger, and `_redacted`
  substitutes one `REDACTED_LINK` for every rule, so a week under the policy would have left a
  count of removed links and no count of lookalike removals. ADR-0015 decision 9 of the same day
  added that count as a log line, and the trigger above names it.
- 2026-09-24: not triggered, both readings taken again. `config.py:67` binds `output_guardrail` to
  `"redact"`, and `_flagged` still reads the lookalike rule as `host_of(normalize_url(url,
  confusables=False))`. The corpus: 1,807 tracked files, 1,781 readable, 2,672 spans reducing to
  1,152 distinct identities, and 10 distinct non-ASCII hosts. They sit in four files,
  `docs/readings/output-guardrail.md` in place of `docs/modules/brain-core.md`, and the lookalike
  rule is unchanged.
