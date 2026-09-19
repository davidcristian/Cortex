# A bounded value leaves the line unbounded

**Status:** done 2026-09-15
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`VALUE_CHARS` bounds one field's value at 2,048 rendered characters. A line has a message and as
many fields as its call site attached, so several fields at the bound pass the measured 16 KiB
limit and the line splits exactly as it did before, with `docker compose logs -t` stamping every
piece and `--tail` counting pieces rather than lines (ADR-0051 decision 12).

That the bound is the limit divided by eight was the argument that this cannot happen today, and it
is an argument rather than a check. It was also weaker than it first read: eight fields at the
bound come to 16,384 characters against a limit of 16,383, one over before a `key=`, a separator, a
marker or the message is counted. Measured through the shipped formatter, seven cut fields make a
line of about 14,500 characters and eight one of about 16,600, so the real headroom is seven
(ADR-0051 decision 13). Only that field count is portable between runs: the exact widths move by
tens of characters with the level, logger and message a line opens with and with the digits in each
cut marker, which is why three runs of this shape recorded 14,536, 14,494 and 14,526.

Which of the two shipped sinks writes the wide line is what this entry first had backwards. It
called the recall trail the widest line the brain writes, and that holds only for what a live stack
has been read writing. Four of the tool audit's fields contain text no call site chose: `tool`,
`call_id` and `arguments` are the model's own, and `error` is what the dispatch or a sidecar
answered, which for an unknown tool is `unknown tool {name!r}` and therefore the model's string
again. All four can be past the bound at once, from one emitted call. Both sinks have eleven keys
at their widest.

The fix is a whole-line bound in `render_fields`, the one place that sees every pair at once, and
its awkward half is that cutting the line drops whole fields and a reader cannot tell a dropped
field from one nobody attached unless a count goes with it. The cheaper alternative is a test:
assert that the widest line any shipped sink builds stays under the limit.

## History

- 2026-08-20: Opened by the close of [R-324](324-a-rendered-field-has-no-bound.md), which bounded a
  value against a measurement of the whole line and left the whole line unmeasured.
- 2026-08-20: The headroom was corrected from eight fields to seven, measured rather than argued
  (ADR-0051 decision 13). The entry is otherwise unchanged.
- 2026-08-21: The tool audit line grew by three keys (the chat, turn and subagent task a dispatch
  was made for, ADR-0009 decision 16), making nine keys on a line with all three. All three are
  short ids and none approaches the per-value bound.
- 2026-08-27: The widest real line was measured at last
  ([R-453](453-the-harness-reads-one-field-off-a-line-it-has-whole.md), ADR-0051 decision 16). Over
  466 recall-trail lines from a live stack, the widest line the brain writes renders at 1,800
  characters against the 16,383 limit, and arithmetic over the shipped caps puts the widest this
  deployment could write near 2,200.
- 2026-09-08: Checked again and not fired, and the headroom is smaller than the last reading said,
  because that reading was of the wrong line. Through the shipped `PlainFormatter`, a
  `LoggingAuditSink`-shaped record whose `tool`, `call_id`, `arguments` and `error` each contain a
  million characters makes a line of 8,580 characters with four cut markers, 52% of the 16,383
  limit and a headroom factor of 1.91. The recall trail at its shipped caps, twenty dropped
  candidates and five hits with uuid4 ids, renders at 2,264 on the same run. So the widest line a
  live stack was read writing, 1,800 characters, is not the widest this deployment could write.
  Seven fields at the bound make 14,494 characters and eight make 16,562, so seven is still the
  headroom in fields.
- 2026-09-12: Checked again and not fired, and the two documents that still had the claim this
  entry disproved are corrected. Re-measured, the audit-shaped record renders at 8,437 characters,
  51.5% of the limit and a headroom factor of 1.94; the recall trail at its shipped caps renders at
  2,258; seven fields at the bound make 14,526 characters and eight make 16,598. Both sinks were
  counted again off their own `extra=` dicts and both still have eleven keys at their widest.
  `docs/modules/repo-checks.md` and `docs/runbooks/memory-pgvector.md` now name the tool audit and
  give both figures. The live half was not re-read, `just recall-width` needing the card a long
  measurement was using, so the 1,800-character reading of 2026-08-27 is still the only live one.
- 2026-09-14: Checked again and not fired, and every in-process figure recomputed. The audit-shaped
  record is 8,573 characters, 52.3% of the limit and a headroom factor of 1.91; the recall trail at
  its shipped caps renders at 2,256; seven fields at the bound make 14,571 characters and eight
  make 16,647. Both sinks still have eleven keys at their widest, the audit's being `tool`, `ok`,
  `arguments`, `trust`, `at`, whichever of the five work identities the dispatch had, and `error`.
  The three absolute widths recorded for one shape, 8,580, 8,437 and 8,573, sit within 1.7% of each
  other and move with the level, logger and message a run chose, which is why the field count is
  the reading that transfers.
- 2026-09-15: Fixed as the cheaper of the two options, and the count of the wide fields was wrong
  by one. `brain/packages/orchestrator/tests/test_widest_line.py` keeps the widest line each
  shipped sink builds under the limit: one case per sink, each driving the real sink rather than
  assembling a record, each setting every field whose text the brain does not choose past
  `VALUE_CHARS`, each asserting the rendered width, the fields the bound cut and the eleven keys on
  the line. It sits in the orchestrator's suite because the composition root is the one place both
  sinks are visible at once. The whole-line bound in `render_fields` was declined, its cost being a
  dropped-field count inside a rendering the function does not own. The correction is the fifth
  field: `session_id` is not one a call site chose either, arriving as a proto string on
  `ClientEvent`, reaching the dispatch stamp, and length-checked nowhere between the wire and
  `render_value`, so a body that sends a two-kilobyte session id puts a fifth cut field on every
  audit line the turn writes. Measured today, the audit's widest line is 10,593 characters, 65% of
  the limit and a headroom factor of 1.55, against the 8,437 and the 1.91 recorded over four
  fields; the recall trail's widest is 4,464 against 2,258 for the same record with an ordinary
  session id. Seven fields at the bound is still the headroom and five of the seven is what the
  widest sink uses. The live half was not run, so the 1,800 characters of 2026-08-27 is still the
  only reading off a running stack, and the in-process figures are an upper bound over it rather
  than a competing reading. Recorded in ADR-0051 decision 15. It opened
  [R-671](671-the-widest-line-check-names-its-sinks-by-hand.md), the two cases naming their sinks
  by hand where the set could be computed.
