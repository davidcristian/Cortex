# The decode-rate line withholds its own numbers

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-17

The deep model's decode-rate lines (`brain/packages/core/src/cortex_core/brain_phase.py`, the
measured line and the spilled warning) attach `tokens`, `tokens_per_second` and
`floor_tokens_per_second`. Every one of those names contains `token`, which is in `SECRET_NAMES`
(`cortex_core/log_secrets.py`), and the rule is a substring match, so the formatter prints all
three as `<redacted>`. Run on 2026-09-17 through `PlainFormatter`, a record carrying `tokens=812`,
`tokens_per_second=41.5` and `floor_tokens_per_second=30.0` printed
`floor_tokens_per_second=<redacted> tokens=<redacted> tokens_per_second=<redacted>`. The swap
runbook (`docs/runbooks/model-swap.md`, the two decode-rate samples) tells an operator to read
those three fields as numbers, and `samplecheck.py` compares field names only, so no gate fails.

The formatter's docstring defends the substring match on the ground that a withheld count "costs
a reader one number they can recover from the message". On this line the three numbers are the
whole reading and the message carries none of them.

**What would be built.** One of two remedies, decided in an addendum. Either rename the three
fields to names the rule does not match (for instance `decoded`, `decode_rate` and `floor_rate`),
which changes the runbook samples and the tests pinning them; or narrow the rule, for instance to
match `token` only as a whole word of the name (`api_token`, `authToken`) and never inside
`tokens`, which then needs a plural rule for `passwords`, `secrets` and `credentials` and a
census of every name the tree attaches. Renaming is the smaller change and leaves the rule as
predictable as it is; narrowing fixes every future count named for tokens too.

## Trail

- 2026-09-17: filed by the ADR-0009 nested-secret addendum, whose census of the names the secret
  rule matches found these three.
