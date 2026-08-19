# A rendered field has no bound on its length

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a line in `docker compose logs brain` that scrolls past a screen, or any adapter that
attaches a value it did not build itself
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`cortex_core/log_fields.py` decides what a field's value looks like and never how much of it there
is. A string is printed whole, quoted if it carries whitespace; a structure is printed as compact
JSON, however deep. So an `extra` carrying a model's reply, a tool result, or a recalled memory
would print all of it, and the recall trail's care to log a query's *length* rather than its text
would be undone by the first adapter that attaches the text under some other name.

Nothing does that today, which is why this is filed rather than fixed: every field the tree
attaches is an id, a count, a flag, an endpoint or a short error detail, and the two per-line
trails were designed against exactly this risk. The defence that exists is about secrecy rather
than size, a denylist of names plus a URL's credential stripped from the line, and neither notices
a field that is merely enormous.

The shape a fix would take is a per-value character bound with a visible marker for what was cut,
applied in `render_value` so both renderings inherit it, and a number chosen against what a
terminal and `docker compose logs` actually do with a long line rather than picked. The awkward
part is the one worth deciding deliberately: truncating a structure's JSON leaves text that no
longer parses, so a bound has to either cut the rendered string and say so, which costs
pasteability on exactly the lines that had it, or drop whole elements, which costs the reader the
knowledge that anything was dropped unless a count rides along the way `dropped_omitted` does.

## Trail

- 2026-08-19: Opened by the close of
  [R-317](317-shipped-handler-drops-every-field.md), which put the secret defence in the formatter
  and left the volume question beside it deliberately untouched.
