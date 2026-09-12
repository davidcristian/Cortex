# A bounded value leaves the line unbounded

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a line whose fields together pass 16,383 rendered characters, which is where a
container's log driver ends one message and starts another. Two readings answer it. `just
recall-width` reports the widest line a live stack wrote, off captures the recall trail produced;
the widest line the tree can build is read off the two shipped sinks by rendering
`LoggingAuditSink`'s eleven fields through `PlainFormatter` with the four a model or a tool server
writes each past `VALUE_CHARS`. This entry's trail records both when they were last taken.
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-12

`VALUE_CHARS` bounds one field's value at 2,048 rendered characters. A line carries a message and
as many fields as its call site attached, so **eight** fields at the bound pass the measured 16 KiB
cliff and the line splits exactly as it did before, with `docker compose logs -t` stamping every
piece and `--tail` counting pieces rather than lines (ADR-0038 bounded-value addendum).

That the bound is the cliff divided by eight is the argument that this cannot happen today, and it
is an argument rather than a check. It is also a weaker argument than it first read: the addendum
that landed the bound claimed eight fields at it still leave a line whole, and eight come to 16,384
characters against a cliff of 16,383, one over before a `key=`, a separator, a marker or the
message is counted. Measured through the shipped formatter, seven cut fields make a line of about
14,500 characters and eight one of about 16,600, so the real headroom is seven (ADR-0038
cut-defeats-withholding addendum). Only that field count carries between runs: the exact widths move
by tens of characters with the level, logger and message a line opens with and with the digits in
each cut marker, which is why three runs of this shape have recorded 14,536, 14,494 and 14,526.
Nothing measures the widest line the tree can actually produce,
and nothing fails when a new sink attaches an eighth large field. Both shipped sinks carry eleven
keys at their widest: the recall trail always writes eleven, and the tool audit writes `tool`,
`ok`, `arguments`, `trust` and `at`, then whichever of the five work identities the dispatch
carried, then `result_chars` or `error`.

Which of the two lines is the wide one is the part this entry's own trail had backwards. It called
the recall trail the widest line the brain writes, and that holds only for what a live stack has
been read writing. Four of the tool audit's fields carry text no call site chose: `tool`, `call_id`
and `arguments` are the model's own, and `error` is what the dispatch or a sidecar answered, which
for an unknown tool is `unknown tool {name!r}` and therefore the model's string again. All four can
be past the bound at once, from one emitted call, and the line that results is several times wider
than any trail line.

The fix has a shape and a cost. `render_fields` is where a whole-line bound would go, since it is
the one place that sees every pair at once, and the awkward half is the same one the per-value bound
decided: cutting the line drops whole fields, and a reader cannot tell a dropped field from a field
nobody attached unless a count rides along, which `render_fields` can add because that function does
own its line. The cheaper alternative is a test rather than a bound: assert that the widest line any
shipped sink builds stays under the cliff, which catches the field that pushes a line over it on the
day that field is written rather than the day the line is read.

## Trail

- 2026-08-20: The headroom this entry inherited was corrected from eight fields to seven, measured
  rather than argued (ADR-0038 cut-defeats-withholding addendum). The entry is unchanged in
  substance: the line is still unbounded and still unmeasured, and the cheaper alternative below, a
  test rather than a bound, is now one field cheaper to trip.
- 2026-08-20: Opened by the close of [R-324](324-a-rendered-field-has-no-bound.md), which bounded a
  value against a measurement of the whole line and left the whole line unmeasured.
- 2026-08-21: The tool audit line grew by three keys (the chat, turn and subagent task a dispatch
  was made for, ADR-0009 named-work addendum), which makes it nine keys on a line carrying all
  three. All three are short ids and none of them approaches the per-value bound, so the headroom
  argument is unchanged in substance; what matters is that this entry's count of the audit trail's
  keys was already a claim nobody re-measured, and the line an operator reads is still unmeasured at
  its widest.
- 2026-08-27: the widest real line is measured at last, which is what this entry's trigger was
  stated in the absence of ([R-453](453-the-harness-reads-one-field-off-a-line-it-has-whole.md),
  ADR-0038 whole-line addendum). Over 466 recall-trail lines from a live stack, the widest line the
  brain writes renders at **1,800 characters against the 16,383 cliff**, and arithmetic over the
  shipped caps puts the widest this deployment could write near 2,200. This entry is unchanged in
  substance: the line is still unbounded and still ungated, and the fix and its cheaper alternative
  both stand. What changed is that the cheaper one, a test asserting the widest line a shipped sink
  builds stays under the cliff, now has a measured figure to be written against.
- 2026-09-08: trigger swept and not fired, and the headroom is a good deal smaller than the last
  reading said, because the last reading was of the wrong line. Rendered through the shipped
  `PlainFormatter` today, a `LoggingAuditSink`-shaped record whose `tool`, `call_id`, `arguments`
  and `error` each carry a million characters makes a line of **8,580 characters** with four cut
  markers on it, which is 52% of the 16,383 cliff and a headroom factor of 1.91. The recall trail
  at its shipped caps, twenty dropped candidates and five hits with uuid4 ids, renders at 2,264 on
  the same run, which is the near-2,200 the whole-line addendum computed. So the widest line a live
  stack was read writing, 1,800 characters, is not the widest this deployment could write, and the
  factor of nine recorded against it belongs to the trail alone. The arithmetic the bound rests on
  is unchanged: measured the same way, seven fields at the bound make a line of 14,494 characters
  and eight make one of 16,562, so seven is still the headroom in fields. Those two counts are the
  ones the cut-defeats-withholding addendum reports as 14,536 and 16,607, over longer field names:
  eight-character keys reproduce 14,536 exactly here, so the difference is the names each run chose
  and not the formatter. The entry stays open and
  its cheaper alternative is now the more attractive of the two: a test asserting the widest line a
  shipped sink builds stays under the cliff has two figures to be written against, and the tool
  audit is where it would bite first.
- 2026-09-12: trigger swept again and not fired, and the two live documents that still carried the
  claim this entry disproved are corrected. Re-measured through the shipped `PlainFormatter` today,
  the widest line the tree can build, the audit-shaped record with a million characters in each of
  its four model-written fields, renders at **8,437 characters, 51.5% of the 16,383 cliff and a
  headroom factor of 1.94**; the recall trail at its shipped caps renders at 2,258; seven fields at
  the bound make 14,526 characters and eight make 16,598, so seven is still the headroom in fields.
  Both sinks were counted again off their own `extra=` dicts and both still carry eleven keys at
  their widest. `docs/modules/repo-gates.md` and `docs/runbooks/memory-pgvector.md` each still said
  the recall trail is the widest line the brain writes, which is what the 2026-09-08 reading
  disproved, so both now name the tool audit and carry both figures. That is the doc half of a
  reading already recorded here and not a bound: the line is still unbounded, still ungated, and the
  cheaper alternative still stands. The live half was not re-read, `just recall-width` needing the
  card that a long measurement was holding all session, so the 1,800-character live reading of
  2026-08-27 remains the only one taken off a running stack.
