# A subagent server started outside compose is held by one value and not by the rule

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a second hand-started subagent server appears in a runbook or a host task, or one of
the two flags the constant registry does not hold is found missing from the one that exists
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-27 by the close of
[R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which held every subagent
server a composed stack starts to the flags its tier requires.

`docs/runbooks/subagents-cpu.md` hands an operator a `docker run` that brings up a standalone CPU
subagent server on loopback, outside any stack, carrying `--jinja`, the template kwarg and
`--reasoning-budget 0`. A gate over compose services cannot see it. What reaches it today is one
constant-registry needle over the budget's count, which came out of the same close: retune the
tier's zero and that command block reddens. The two other flags are held there by nobody, so an
edit that dropped the kwarg from the operator's command would leave the runbook telling somebody to
start a server the shipped stack would not.

**Why it was left.** The scale is one command block in one runbook, and the shapes a fenced shell
line can take are the reason `samplecheck.py` exists as its own gate. Teaching the flag rule to
read fenced commands is a second reader for one far side.

**What would close it.** Most likely two more needles rather than a reader: the kwarg and the
`--jinja` are each a fixed string, and a constant they could hang off already exists in the
sidecar's `_REASONING_OFF`. The alternative worth weighing first is that a runbook command is
prose an operator adapts, and holding three flags in it is holding a paste.

## Trail

- 2026-08-27: opened by the close of
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), whose gate reaches
  compose services and whose registry entry reaches this command block's budget alone.
