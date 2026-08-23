# A needle's own literal reddens the entry beside the value that moved

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Opened 2026-08-23 by the close of
[R-396](396-the-seam-host-rides-inside-the-ports-needles.md), which registered the brain's bind
host and measured what the loopback digits inside two dozen other needles actually do.

A mention's template is shape plus one rendered value, and the shape is made of the neighbouring
text, some of which is somebody else's value. When that neighbour moves, the needle is unfound and
`crosscheck.py` reports the entry the needle belongs to. Two plantings showed it: moving
`docker/docker-compose.yml`'s published host-side interface, and moving
[modules/body-app.md](../../modules/body-app.md)'s `CORTEX_BRAIN_ADDR` default, each printed **the
brain's seam port** is not tied, over a port that had not moved. The reader is sent to
`DEFAULT_SEAM_PORT`, finds it correct, and has to diff the needle by hand to see which of its
literals stopped matching.

**Why it was left.** The close it came out of was about whether a shadowed value is held, and the
answer (it is not, so register it) does not need this. Reporting is a change to the scan rather
than to its data, and it was not going to be designed inside a taxonomy decision.

**What would close it.** Two shapes, and they are not exclusive.

The cheap one is a better fault. When a rendered needle is unfound, the scan already has the
template and the file; it could report which **span** of the rendered needle the file does not
carry, or simply the longest prefix that still matches, which points at the literal that moved
without knowing anything about values. That is a message change and a few branches.

The expensive one removes the shadow instead of explaining it: let a template render a **registered
neighbour's** value, so ``"{value}:{value}"`` on the compose publish becomes a needle over two
entries and each side is read from its own declaration. Read the cost before writing it. It makes
one mention depend on another entry, which is a new edge in a registry that has none, and it wants
an answer for what happens when the neighbour's own entry is the one that is failing. The cheap
shape may make the expensive one unnecessary, which is the order to try them in.

## Trail

- 2026-08-23: filed by the close of
  [R-396](396-the-seam-host-rides-inside-the-ports-needles.md), which measured the misattribution
  while settling that a value carried as a needle's literal is shadowed rather than held.
- 2026-08-23: landed as the cheap shape, in a new `scripts/needles.py` holding the mention's side
  of the scan. **The expensive shape was not deferred, it was refused**: both measured neighbours
  are unregistered on purpose, the close that filed this having counted `127.0.0.1` as five values
  and held one, so a template rendering a registered neighbour could not have reached either case
  without first registering four values that ruling had just declined. **And this entry's own
  proposal was wrong in its stronger half.** It offered "the longest prefix that still matches,
  which points at the literal that moved"; a run is measured over a file and not a line, so a
  prefix satisfied elsewhere overstates it, and on the flagship case itself the redis publish
  carries `"127.0.0.1:` after the seam publish's interface moves. The claim that carries the fault
  is therefore whether the file still spells this constant's own value as a token of its own, with
  the run kept as a second, weaker reading. Three plantings before and after on the real tree, two
  of them the misattributed cases and one a control where the value really moved; tabled in the
  ADR-0023 misattributed-fault addendum. Two residues filed: a counted mention that finds nothing
  gets none of this ([R-405](405-a-counted-mention-that-finds-nothing-says-nothing.md)), and the
  run's own overstatement ([R-406](406-the-carried-run-is-measured-over-a-whole-file.md)).
