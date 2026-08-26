# The hosted subagent tier meets the flag rule by hand rather than by the rule

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-27 by the close of
[R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which derived the set of
subagent servers a composed stack starts and held every one of them to the flags the tier requires.

`flagcheck.py` reads compose services, so the model host's own hosted subagent tier is out of its
reach by design: that tier is a child process the supervisor starts, and its argv is assembled in
`brain/packages/model_manager/src/cortex_model_manager/tiers.py` from `TierArgs`. It does carry all
three flags today, `_JINJA` for every tier and `_REASONING_OFF` on the subagent one, and the
model_manager roster suite pins that argv whole, so nothing is currently wrong. What is missing is
the same thing R-462 was filed for, one level down: **the sidecar's subagent tier is a position in
a fixed three-entry tuple, not a set anything reads**. A fourth tier added to `tiers()` for a
second subagent pick would carry whatever its author copied, and the suite pinning today's three
would go on passing for the three it names.

The two halves also spell one requirement twice. `flagcheck.REQUIREMENTS` says a subagent server
carries `--jinja` and the reasoning-off pair; `config.py` says it with `_JINJA` and
`_REASONING_OFF`. Only the budget's count is tied, by the constant registry.

**Why it was left.** The close it came out of had a compose reader to build and a gate to prove,
and this needs a different reader: the sidecar builds its argv in Python, so answering "which of
these tiers serves subagents" means reading a dataclass construction rather than a YAML block.
Building an unproven Python reader inside the pass that proved the compose one would have put the
two under one mutation table.

**What would close it.** Either a reading of the sidecar's own tiers that feeds the same
`REQUIREMENTS`, so one rule covers both placements of one tier, or the honest argument that the
model_manager suite is the right holder and what is owed instead is a check that every tier whose
id names a subagent carries `_REASONING_OFF`. The second is cheaper and should be argued against
before the first is built.

## Trail

- 2026-08-27: opened by the close of
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which reached every
  subagent server compose starts and left the one the supervisor starts to its own suite.
