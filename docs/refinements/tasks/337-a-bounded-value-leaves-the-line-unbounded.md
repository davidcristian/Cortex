# A bounded value leaves the line unbounded

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a line whose fields together pass 16,383 rendered characters, which is where a
container's log driver ends one message and starts another
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`VALUE_CHARS` bounds one field's value at 2,048 rendered characters. A line carries a message and
as many fields as its call site attached, so nine fields at the bound pass the measured 16 KiB
cliff and the line splits exactly as it did before, with `docker compose logs -t` stamping every
piece and `--tail` counting pieces rather than lines (ADR-0038 bounded-value addendum).

That the bound is the cliff divided by eight is the argument that this cannot happen today, and it
is an argument rather than a check. Nothing measures the widest line the tree can actually produce,
and nothing fails when a new sink attaches a tenth large field. The audit trail already carries ten
keys, most of them small; the recall trail carries eleven.

The fix has a shape and a cost. `render_fields` is where a whole-line bound would go, since it is
the one place that sees every pair at once, and the awkward half is the same one the per-value
bound decided: cutting the line drops whole fields, and a reader cannot tell a dropped field from a
field nobody attached unless a count rides along, which `render_fields` can honestly add because
that function does own its line. The cheaper alternative is a test rather than a bound: assert that
the widest line any shipped sink builds stays under the cliff, which catches the tenth field on the
day it is written rather than the day it is read.

## Trail

- 2026-08-20: Opened by the close of
  [R-324](324-a-rendered-field-has-no-bound.md), which bounded a value against a measurement of the
  whole line and left the whole line unmeasured.
