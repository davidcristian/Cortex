# The tool audit line is described in prose because its fields vary by condition

**Status:** landed 2026-09-05
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-09-02 by the close of
[R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), which read the deep phase's
composed field lists and decided that the tool audit's stays unread.

`brain/packages/tools/src/cortex_tools/audit.py` binds `fields`, grows it by `update` with
whichever of the five work identities the dispatch carried, gives it `result_chars` or `error` by
whether the call succeeded, and hands it to `_logger.info`. No one sample can print what that
attaches, because what it attaches is a set that varies by condition, so `logfields.py` refuses it
at the first use after its binding rather than reading the five-key literal as the line. What the
tools runbook says about the line, `docs/runbooks/tools-mcp.md` describing the tool's name, `ok`,
the arguments, `trust`, either `result_chars` or `error` and the work identities, is therefore held
by nothing, which is the shape the swap runbook's warning bullet drifted into before it was
printed: six names in an order the formatter does not print and three missing.

The drift the entry was opened against was already there and is now corrected: the runbook's
enumeration named eleven of the line's twelve possible fields and left `at` out, where the sink
attaches it on every call and the ADR's own arithmetic for this line counts it (five fixed fields,
five work identities, and one of `result_chars` or `error`, which is the "up to eleven" a rendered
line reaches). The module contract in `docs/modules/brain-tools.md` names the timestamp, the sink's
suite asserts it in all four of its rendered lines, and the runbook alone did not. That is the
condition this entry was waiting on, so what remains is the tie rather than the fix.

Two ways to close it. A sample grammar for a field present by condition, say one sample per
condition with the reader following the `if` that sets the field, which is the branch-following
the entry above declined and would need the reader to say which branch a sample stands for. Or the
sink's own suite, `brain/packages/tools/tests/test_audit.py`, which asserts four whole rendered
lines already and could be named by the registry beside the runbook's field list the way the
declared-name addendum names it beside the message, so the prose and the assertion are tied by a
needle. The second costs one registry entry per field and holds the names, not the conditions.

## Trail

- 2026-09-02: opened by the close of
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), which measured the audit
  line refused as bound at line 65 and used again at line 72, and left its prose where it was.
- 2026-09-04: the first half of the trigger fired and the entry becomes actionable. Reading the
  runbook's enumeration against the sink found one field missing, `at`, which the sink attaches on
  every call: the prose named the tool, `ok`, the arguments, `trust`, either `result_chars` or
  `error`, the four work ids and `call_id`, eleven of the twelve names a line can carry. The
  sentence is corrected to name the timestamp, so the prose and the sink agree again, and the
  refinement itself is untouched: nothing still holds them together, and the next drift will be as
  quiet as this one. The second half has not fired. Reading the `extra=` of every brain log call
  and following the seven that name a binding finds six read cleanly and one refused, the audit
  sink's at line 89, bound at line 65 and used again at line 72, so this is still the only line in
  the brain whose field set varies by condition.
- 2026-09-05: **landed**, by neither proposed close (ADR-0009 proven-line addendum). Re-derivation
  held every count: 94 `extra=` expressions, seven naming a binding, six read and one refused at
  `audit.py:89`, twelve possible names. What the entry had wrong is its second close: a registry
  entry needs a declaring site, seven of the twelve names are literal keys declared nowhere, the
  runbook's sentence named ten of them and described two in prose, `session_id` had no
  tools-runbook mention at all, and a needle holds a name and never a set, so a field the sink
  gained would have missed nothing. The tie landed instead is a chain: the runbook prints five
  rendered samples of the line, one per shape, and `scripts/samplecheck.py` holds each to a whole
  line the sink's own suite asserts against the shipped formatter (`scripts/assertedlines.py`),
  which pytest holds to the sink. Measured over the gate suite (1,709 checks), `check-samplecheck`
  (12 samples, 5 held to the suite) and the sink's suite (13 checks): a field dropped from a
  sample, a sample reordered, a field the sink gained or renamed with the suite updated, and a
  suite assertion loosened to a containment each fail the gate. Opened
  [R-553](553-which-condition-a-printed-audit-sample-stands-for-is-prose-beside-the-fence.md) for
  the sentence saying which shape each sample is, and
  [R-554](554-a-whole-line-asserted-through-an-f-string-or-a-helper-is-not-read-as-proven.md)
  for the assertion shapes the reader leaves unread.
