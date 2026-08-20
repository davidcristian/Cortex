# Packed values keep their whole length

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a deployment that really sets `CORTEX_LOG_FORMAT=packed`, or a collector in front of
it that reads entries rather than lines
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The per-value bound landed in `render_value`, which only the plain rendering spends.
`PackedFormatter` hands `record_fields(record)` straight to `json.dumps`, so a field of any size
reaches a packed line whole, and the two renderings now share the secrets rule and nothing else.

The asymmetry was argued rather than overlooked (ADR-0038 bounded-value addendum): the whole value
of a rendering meant to be collected is that the object parses, and a bound inside it either
corrupts the object or lies about its shape, which is the argument for cutting the plain rendering
running the other way. What is not settled is that the exposure goes away with it. A collector
meets the same 16 KiB message split the plain reader does, one JSON object arriving as several
entries, and the one that reassembles them is `docker compose logs` rather than anything
downstream of it.

Three shapes are available and none is obviously right. The line could carry the bound as a
sibling key, say `fields_cut`, naming the fields that were shortened, which keeps the object
parseable at the cost of a key nothing else uses. The packed rendering could pass values through
`render_value` and become a line of rendered strings, which is a different rendering rather than a
bounded one. Or the bound could stay a plain-rendering rule and the packed one could be documented
as unbounded on purpose, which is where it stands today and is only honest while nobody runs it.

## Trail

- 2026-08-20: The second shape below gained an argument nobody was looking for. `render_value` now
  withholds a URL credential before the bound cuts, because a cut between a `://` and its `@`
  defeated the whole-line pass entirely (ADR-0038 cut-defeats-withholding addendum). The packed
  rendering never had that exposure, having no cut, so nothing here is more urgent; but a packed
  line routed through `render_value` would inherit the ordering rather than need it written twice.
- 2026-08-20: Opened by the close of
  [R-324](324-a-rendered-field-has-no-bound.md), which bounded the rendering an operator reads and
  deliberately left the one a collector reads alone.
