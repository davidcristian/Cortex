# A bounded value leaves the line unbounded

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a line whose fields together pass 16,383 rendered characters, which is where a
container's log driver ends one message and starts another
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`VALUE_CHARS` bounds one field's value at 2,048 rendered characters. A line carries a message and
as many fields as its call site attached, so **eight** fields at the bound pass the measured 16 KiB
cliff and the line splits exactly as it did before, with `docker compose logs -t` stamping every
piece and `--tail` counting pieces rather than lines (ADR-0038 bounded-value addendum).

That the bound is the cliff divided by eight is the argument that this cannot happen today, and it
is an argument rather than a check. It is also a weaker argument than it first read: the addendum
that landed the bound claimed eight fields at it still leave a line whole, and eight come to 16,384
characters against a cliff of 16,383, one over before a `key=`, a separator, a marker or the
message is counted. Measured through the shipped formatter, seven cut fields make a line of 14,536
characters and eight make one of 16,607, so the real headroom is seven (ADR-0038
cut-defeats-withholding addendum). Nothing measures the widest line the tree can actually produce,
and nothing fails when a new sink attaches an eighth large field. The audit trail already carries
ten keys, most of them small; the recall trail carries eleven.

The fix has a shape and a cost. `render_fields` is where a whole-line bound would go, since it is
the one place that sees every pair at once, and the awkward half is the same one the per-value
bound decided: cutting the line drops whole fields, and a reader cannot tell a dropped field from a
field nobody attached unless a count rides along, which `render_fields` can honestly add because
that function does own its line. The cheaper alternative is a test rather than a bound: assert that
the widest line any shipped sink builds stays under the cliff, which catches the tenth field on the
day it is written rather than the day it is read.

## Trail

- 2026-08-20: The headroom this entry inherited was corrected from eight fields to seven, measured
  rather than argued (ADR-0038 cut-defeats-withholding addendum). The entry is unchanged in
  substance: the line is still unbounded and still unmeasured, and the cheaper alternative below,
  a test rather than a bound, is now one field cheaper to trip.
- 2026-08-20: Opened by the close of
  [R-324](324-a-rendered-field-has-no-bound.md), which bounded a value against a measurement of the
  whole line and left the whole line unmeasured.
- 2026-08-21: The tool audit line grew by three keys (the chat, turn and subagent task a dispatch
  was made for, ADR-0009 named-work addendum), which makes it nine keys on a line carrying all
  three. All three are short ids and none of them approaches the per-value bound, so the headroom
  argument is unchanged in substance; what is worth noting is that this entry's count of the audit
  trail's keys was already a claim nobody re-measured, and the line an operator reads is still
  unmeasured at its widest.
