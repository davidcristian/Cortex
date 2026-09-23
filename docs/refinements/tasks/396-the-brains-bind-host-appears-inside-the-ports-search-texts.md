# The brain's bind host appears inside the port's search texts and nothing checks it

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`RpcServerConfig.host` defaults to `127.0.0.1`
(`brain/packages/orchestrator/src/cortex_orchestrator/config.py`, line 56), and every search text
that now covers the port writes that address as part of its own template:
`"127.0.0.1:{value}:{value}"`, `` `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:{value}`) ``,
`insecure_channel("127.0.0.1:{value}")` and nine more. The port cannot change unnoticed. The host
can move and leave all twelve search texts unmatched at once, which the check would report as
twelve ports that stopped agreeing, naming the wrong value in every message.

It has no declaration to read. The port is a module-level constant so this scan can read it; the
host is an indented pydantic field, and `crosscheck.py`'s Python declaration form is anchored at
column 0, so a field cannot be a declaration without hoisting a constant. That is a change to the
brain's config module rather than a registry row.

The remedy is to hoist the host to `DEFAULT_RPC_HOST` beside `DEFAULT_RPC_PORT`, then decide
whether the host and the port are one coupling or two. They are two: they move for different
reasons, an operator binding `0.0.0.0` changes one and not the other, and the compose stack already
publishes on a host half that differs from the container half.

## History

- 2026-08-23: opened by the close of
  [R-389](389-the-brain-port-is-held-in-code-and-not-in-prose.md), which found the loopback address
  written as fixed text inside twelve of the port's own search texts while nothing checked it as a
  value.
- 2026-08-23: closed as `DEFAULT_RPC_HOST` hoisted beside the port and one entry over three
  places, not twelve. The entry was wrong about which value those search texts contain. There are
  24 of them, not twelve (18 on the brain's port, 6 on the body's listen port, which the entry
  never mentions), and the digits in them are five different values: the brain's bind default, the
  body's bind default, the two `CORTEX_*_ADDR` client defaults, the compose publish's host-side
  interface and a handful of loopback dials. The shipped stack settles it:
  `docker/docker-compose.yml` sets `CORTEX_SEAM_HOST=0.0.0.0`, so the container this repo ships
  does not bind `127.0.0.1` at all. Retune the default and exactly one of the 24 is stale, so the
  predicted failure, twelve unmatched search texts naming twelve ports, would have been a false
  failure twelve times over. The ruling: a value that only appears incidentally inside another
  entry's search text is not checked, on three properties and a fourth that decides the remedy. The
  comparison runs against the registry's own text rather than a declaration; it can fail only where
  the restating place moved; the message names the wrong constant, measured, since moving the
  compose publish's interface or the body app contract's dial default each makes the port entry
  fail; and an incidental appearance is no evidence the value is there. So a value is checked by
  having an entry of its own, and a new entry's search texts include only their own value where the
  shape allows: the RPC contract's one line is covered once from each end. Seven planted changes,
  four proving the entry and three the misattribution, with two controls green; the ruling is
  ADR-0042 decision 25. The registry took a ninth part, `endpointcouplings.py`, at the line cap. One
  residue filed: the message that names the wrong entry
  ([R-403](403-an-unmatched-search-text-fails-the-wrong-entry.md)).
