# An unmatched search text fails the entry beside the value that actually moved

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

A match template is a shape plus one rendered value, and the shape is made of the neighbouring
text, some of which is somebody else's value. When that neighbour moves, the search text is not
found and `crosscheck.py` reports the entry the search text belongs to. Two planted changes showed
it: moving `docker/docker-compose.yml`'s published host-side interface, and moving
[modules/body-app.md](../../modules/body-app.md)'s `CORTEX_BRAIN_ADDR` default, each printed that
the brain's port is not tied, over a port that had not moved. The reader is sent to
`DEFAULT_RPC_PORT`, finds it correct, and has to diff the search text by hand to see which of its
literals stopped matching.

Two remedies, not exclusive. The cheap one is a better message: when a rendered search text is not
found, the scan already has the template and the file, so it can report which span of the rendered
text the file does not contain, or the longest prefix that still matches, which points at the
literal that moved without reference to values at all. The expensive one removes the overlap: let a
template render a registered neighbour's value, so `"{value}:{value}"` on the compose publish
becomes a search text over two entries, each side read from its own declaration. That makes one
match depend on another entry, which is a new edge in a registry that has none, and it needs an
answer for what happens when the neighbour's own entry is the failing one.

## History

- 2026-08-23: filed by the close of
  [R-396](396-the-brains-bind-host-appears-inside-the-ports-search-texts.md), which measured the misattribution
  while settling that a value appearing only inside another entry's search text is not checked.
- 2026-08-23: closed as the cheap remedy, in a new `scripts/searchtexts.py` holding the match side
  of the scan. The expensive remedy was rejected rather than deferred: both measured neighbours are
  unregistered on purpose, the close that filed this having counted `127.0.0.1` as five values and
  registered one, so a template rendering a registered neighbour could not have reached either case
  without first registering four values that ruling had just declined. This entry's own proposal
  was also wrong in its stronger half. It offered "the longest prefix that still matches, which
  points at the literal that moved"; a run is measured over a file and not a line, so a prefix
  satisfied elsewhere overstates it, and on the main case the redis publish contains `"127.0.0.1:`
  after the brain publish's interface moves. The claim in the message is therefore whether the file
  still writes this constant's own value as a token of its own, with the run kept as a second,
  weaker reading. Three planted changes before and after on the real tree, two of them the
  misattributed cases and one a control where the value really moved; the reading is ADR-0042
  decision 18. Two residues filed: a counted match that finds nothing gets none of this
  ([R-405](405-a-counted-mention-that-finds-nothing-says-nothing.md)), and the run's own
  overstatement ([R-406](406-the-quoted-run-of-an-unmatched-search-text-covers-a-whole-file.md)).
