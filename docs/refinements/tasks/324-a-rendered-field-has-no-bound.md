# A rendered field has no bound on its length

**Status:** landed 2026-08-20
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`cortex_core/log_fields.py` decides what a field's value looks like and never how much of it there
is. A string is printed whole, quoted if it carries whitespace; a structure is printed as compact
JSON, however deep. So an `extra` carrying a model's reply, a tool result, or a recalled memory
would print all of it, and the recall trail's care to log a query's *length* rather than its text
would be undone by the first adapter that attaches the text under some other name.

Something does that today, which the close of this entry found and this paragraph originally
denied: the tool audit attaches `arguments` verbatim, and `spawn_subagents` takes its `instruction`
and `context` from the model, so the unbounded field is on a trail this repo already writes rather
than in a future adapter. The rest of the reading held: every other field the tree attaches is an
id, a count, a flag, an endpoint or a short error detail, and the two per-line trails were designed
against exactly this risk. The defence that exists is about secrecy rather
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

- 2026-08-20: The landing below had a hole in it, found by an independent audit and fixed
  (ADR-0038 cut-defeats-withholding addendum). The bound was applied after the value was rendered
  but before the line's URL withholding ran, and `_USERINFO` ends its match on the `@` that closes
  a userinfo, so a cut falling between a URL's `://` and that `@` printed the credential in full on
  the shipped default rendering. A rendering is now withheld before it is cut. Two smaller things
  went with it: a rendering the bound will cut is quoted rather than left bare, so the marker's
  whitespace no longer writes a field boundary inside a field, and the eight-fields headroom
  claimed below was corrected to the seven that is measurable. One residue opened, the shapes of
  credential the pattern cannot match at all
  ([R-343](343-a-userinfo-the-pattern-cannot-reach.md)).
- 2026-08-20: Landed (ADR-0038 bounded-value addendum). A value is cut at 2,048 rendered
  characters, the measured 16 KiB a container's log driver gives one message divided by eight, with
  `<cut 900 chars>` naming what went. Measured on the shipped image: a rendered line of 16,383
  characters plus its newline is the last that stays one entry, and past that a timestamped
  `docker compose logs` stamps every piece, while `--tail 3` returned one fragment of a value
  34,517 characters long. The
  awkward half was decided against dropping elements, because a count would have to go inside a
  structure this function does not own, and the risk's commonest shape is a string with no elements
  to drop. Two residues opened: the packed rendering
  ([R-336](336-packed-values-keep-their-whole-length.md)) and the line as opposed to the value
  ([R-337](337-a-bounded-value-leaves-the-line-unbounded.md)).
- 2026-08-19: Opened by the close of
  [R-317](317-shipped-handler-drops-every-field.md), which put the secret defence in the formatter
  and left the volume question beside it deliberately untouched.
