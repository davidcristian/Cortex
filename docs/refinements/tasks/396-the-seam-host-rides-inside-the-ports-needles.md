# The seam host rides inside the port's needles as shape, and nothing holds it

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Opened 2026-08-23 by the close of
[R-389](389-the-brain-port-is-held-in-code-and-not-in-prose.md), which registered the brain's seam
port in twenty three places and wrote the address beside it into a dozen of them as literal text.

`SeamServerConfig.host` defaults to `127.0.0.1`
(`brain/packages/orchestrator/src/cortex_orchestrator/config.py`, line 56), and every needle that
now holds the port spells that address as part of its own template: `"127.0.0.1:{value}:{value}"`,
`` `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:{value}`) ``, `insecure_channel("127.0.0.1:{value}")`
and nine more. The port cannot drift. The host can move in the field and leave all twelve needles
unfound at once, which the gate would report as twelve ports that stopped agreeing, naming the
wrong value in every fault.

**Why it was left.** It has no declaration to read. The port is a module-level constant precisely
so this scan can read it; the host is an indented pydantic field, and `crosscheck.py`'s Python
declaration form is anchored at column 0, so a field is not a site and cannot be made one without
hoisting a constant. That is a change to the brain's config module rather than a registry row, and
making it inside a close about the port would have hidden a code change under a taxonomy decision.
The same shape is recorded for the vision mode a few lines above the port, where the hoist was
paid, and its comment says why.

**What would close it.** Hoist the host to `DEFAULT_SEAM_HOST` beside `DEFAULT_SEAM_PORT`, which is
the remedy the compose survey has now paid a dozen times, then decide whether the host and the port
are one coupling or two. They are two: the address and the port move for different reasons, an
operator binding `0.0.0.0` changes one and not the other, and the compose stack already publishes
on a host half that differs from the container half. So the likely shape is a second entry whose
mentions are the same lines read for their other half, which means the templates above would each
be paid twice, once under each entry. Read whether that is worth it before writing it: a needle
that renders both values would tie them into one answer, which is the thing this entry says is
wrong.

## Trail

- 2026-08-23: opened by the close of
  [R-389](389-the-brain-port-is-held-in-code-and-not-in-prose.md), which found the loopback address
  spelled as fixed text inside twelve of the port's own needles while nothing held it as a value.
- 2026-08-23: landed as `DEFAULT_SEAM_HOST` hoisted beside the port and one entry over three
  places, not twelve. **The entry was wrong about which value those needles carry.** There are 24
  of them, not twelve (18 on the seam port, 6 on the body's listen port, which the entry never
  mentions), and the digits in them are five different values: the brain's bind default, the body's
  bind default, the two `CORTEX_*_ADDR` client defaults, the compose publish's host-side interface
  and a handful of loopback dials. The shipped stack settles it: `docker/docker-compose.yml` sets
  `CORTEX_SEAM_HOST=0.0.0.0`, so the container this repo ships does not bind `127.0.0.1` at all.
  Retune the default and exactly one of the 24 is stale, so the predicted failure, twelve needles
  unfound and twelve ports named, would have been a false failure twelve times over. **The ruling:
  an incidentally-pinned value is shadowed rather than held**, on three properties and a fourth
  that decides
  the remedy. The comparison runs against the registry's own text rather than a declaration; it can
  fail only where the far side moved; the fault names the wrong constant, measured, since moving
  the compose publish's interface or the body app contract's dial default each makes the seam
  port's entry fail; and a shadow is not evidence the value is there. So a value is held by having
  an entry, and a new entry's needles carry only their own value where the shape allows: the RPC contract's
  one line is paid once from each end. Seven plantings, four proving the entry and three the
  misattribution, with two controls green; tabled in the ADR-0023 bind-host addendum. The registry
  took a ninth part, `endpointcouplings.py`, on the cap. One residue filed: the fault that names
  the wrong entry ([R-403](403-a-needles-literal-reddens-the-wrong-entry.md)).
