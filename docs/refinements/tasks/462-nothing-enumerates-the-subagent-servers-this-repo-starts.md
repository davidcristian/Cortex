# Nothing enumerates the subagent servers this repo starts, so the pair is held per file by hand

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-460](460-the-reasoning-off-pair-is-spelled-in-three-places.md), which held the reasoning-off
flag pair in the two compose subagent servers by naming each of them in the registry.

The claim a reader wants is that **every** subagent server this repo starts carries both
reasoning-off flags. What the registry holds is narrower: the two servers written down in it do.
The difference is a fourth server, added tomorrow in a new override or in an existing one, which
carries whatever its author remembered and reddens nothing. That is the fault
[R-460](460-the-reasoning-off-pair-is-spelled-in-three-places.md) was filed for, held in one of
its two shapes.

The set is real and readable in principle. A subagent server today is a compose service running
the llama.cpp image whose address the brain's own subagent configuration dials, either as
`CORTEX_SUBAGENTS_ENDPOINT` and `CORTEX_SUBAGENTS_GPU_ENDPOINT` or as the endpoint inside a
`CORTEX_SUBAGENTS_ROSTER__*` object, plus the model host's own subagent tier, which is a child
process rather than a service. `composeservices.py` already reads what a service runs, and
`rostercheck.py` already holds a written list to a set the tree really has.

**Why it was left.** The close it came out of had a deadline and a gate to prove, and the
enumeration is a second gate's worth of work: endpoints resolved across overrides, a JSON roster
value parsed, and one member that is not a compose service at all. Building it inside the pass
that held the two known servers would have put an unproven reader under a proven needle.

**What would close it.** A reader of the subagent servers a composed stack starts, and a check
that each one's command carries the pair, so that registering a server is what a new override
does rather than what its author must remember. If the reader lands, the two mentions in
`subagentcouplings.py` become a value coupling over what the reader found, and the naming half
moves to the roster gate.

## Trail

- 2026-08-26: opened by the close of
  [R-460](460-the-reasoning-off-pair-is-spelled-in-three-places.md), which held the pair as one
  needle per named file and could not reach the set.
