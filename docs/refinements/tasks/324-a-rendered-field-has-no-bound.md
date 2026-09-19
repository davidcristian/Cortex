# A rendered field has no bound on its length

**Status:** done 2026-08-20
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`cortex_core/log_fields.py` decided what a field's value looks like and never how much of it there
is. A string was printed whole, quoted if it contained whitespace; a structure was printed as
compact JSON, however deep. So an `extra` holding a model's reply, a tool result or a recalled
memory printed all of it, and the recall trail's care to log a query's length rather than its text
would be undone by any adapter that attached the text under another name.

One adapter already did: the tool audit attaches `arguments` word for word, and `spawn_subagents`
takes its `instruction` and `context` from the model, so the unbounded field was on a trail this
repo already writes. Every other field the tree attaches is an id, a count, a flag, an endpoint or
a short error detail. The existing defence is about secrecy rather than size, a list of withheld
names plus a URL's credential stripped from the line, and neither catches a field that is merely
enormous.

The fix is a per-value character bound with a visible marker for what was cut, applied in
`render_value` so both renderings inherit it, and a number chosen against what a terminal and
`docker compose logs` do with a long line. The awkward part: truncating a structure's JSON leaves
text that no longer parses, so a bound has to either cut the rendered string and say so, which
costs pasteability on exactly the lines that had it, or drop whole elements, which hides from the
reader that anything was dropped unless a count goes with it the way `dropped_omitted` does.

## History

- 2026-08-19: Opened by the close of [R-317](317-shipped-handler-drops-every-field.md), which put
  the secret defence in the formatter and left the volume question untouched.
- 2026-08-20: Fixed (ADR-0051 decision 12). A value is cut at 2,048 rendered characters, the
  measured 16 KiB a container's log driver gives one message divided by eight, with
  `<cut 900 chars>` naming what went. Measured on the shipped image: a rendered line of 16,383
  characters plus its newline is the last that stays one entry, and past that a timestamped
  `docker compose logs` stamps every piece, while `--tail 3` returned one fragment of a value
  34,517 characters long. Dropping elements was rejected, because a count would have to go inside a
  structure this function does not own, and the commonest case is a string with no elements to
  drop. Two remainders opened: the packed rendering
  ([R-336](336-packed-values-keep-their-whole-length.md)) and the line as opposed to the value
  ([R-337](337-a-bounded-value-leaves-the-line-unbounded.md)).
- 2026-08-20: The fix above had a hole in it, found by an independent audit and repaired (ADR-0051
  decision 13). The bound was applied after the value was rendered but before the line's URL
  withholding ran, and `_USERINFO` ends its match on the `@` that closes a userinfo, so a cut
  falling between a URL's `://` and that `@` printed the credential in full under the shipped
  default rendering. A rendering is now withheld before it is cut. Two smaller changes went with
  it: a rendering the bound will cut is quoted rather than left bare, so the marker's whitespace no
  longer creates a field boundary inside a field, and the eight-field headroom claimed above was
  corrected to the seven that is measurable. One remainder opened, the forms of credential the
  pattern cannot match at all ([R-343](343-a-userinfo-the-pattern-cannot-reach.md)).
