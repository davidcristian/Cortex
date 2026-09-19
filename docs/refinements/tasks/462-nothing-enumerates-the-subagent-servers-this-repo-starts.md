# Nothing enumerates the subagent servers this repo starts, so the flag pair is checked file by file

**Status:** done 2026-08-27
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

The claim a reader wants is that every subagent server this repo starts uses both reasoning-off
flags. What the registry checked was narrower: the two servers named in it do. A fourth server,
added tomorrow in a new override or an existing one, would use whatever its author remembered and
fail nothing.

The set is readable in principle. A subagent server today is a compose service running the
llama.cpp image whose address the brain's subagent configuration dials, either as
`CORTEX_SUBAGENTS_ENDPOINT` and `CORTEX_SUBAGENTS_GPU_ENDPOINT` or as the endpoint inside a
`CORTEX_SUBAGENTS_ROSTER__*` object, plus the model host's own subagent tier, which is a child
process rather than a service. `composeservices.py` already reads what a service runs, and
`rostercheck.py` already compares a written list with the set the tree really has.

## History

- 2026-08-26: opened by the close of
  [R-460](460-the-reasoning-off-pair-is-spelled-in-three-places.md), which checked the pair once
  per named file and could not reach the whole set.
- 2026-08-27: closed as the derived-set rule of
  [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md): an eleventh cross-tree scan,
  `scripts/flagcheck.py`, over the set `scripts/subagentservers.py` derives and the compose syntax
  `scripts/composestarts.py` reads under it. The premise held: the two named servers and the
  unreachable third were where this entry said they were. The set is derived two ways, from the
  wiring that dials a server and from the argv that names its model, each catching a server the
  other misses, and the mutation table shows neither is redundant. `--jinja` joined the pair as a
  requirement, since the rule is what a subagent server must be started with rather than what one
  entry was filed about. The registry's two compose entries are gone and its remaining entry is
  renamed for the budget it still checks, and the runbook's hand-started server was registered as
  the far side that keeps the entry cross-language. Opened by it:
  [R-467](467-the-hosted-subagent-tier-meets-the-flag-rule-by-hand.md) for the tier the supervisor
  starts, and [R-468](468-a-subagent-server-started-outside-compose-is-held-by-a-value.md) for the
  server a runbook starts outside any stack.
