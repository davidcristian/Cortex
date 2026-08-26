# The subagent couplings part sits two lines under the line cap

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** the next coupling written into `scripts/subagentcouplings.py`, which will not fit.

Opened 2026-08-26 by the close of
[R-460](460-the-reasoning-off-pair-is-spelled-in-three-places.md), whose entry took that file from
256 lines to 298.

The cap is 300 and the file is at 298, so the next entry in it fails the line cap rather than
landing. That is the gate working, and it is also a trap for whoever writes that entry: they will
be splitting a registry part while trying to record a coupling, which is the cleanup pass this
contract asks nobody to do in the middle of something else.

**Why it was left.** Splitting a part is not free. `registry.py` names every part in prose held to
the directory and to the order the tuple joins them in, the module contract names the same set,
and the repo map names it again, so a split is four documents and a rostered listing. Doing it
while nothing needs it would have been a refactor riding inside a gate change.

**What would close it.** Either a split of `subagentcouplings.py` on a seam its own docstring can
argue (the four bounds one delegated run stands between are one subject; the container asks and
budgets are another; the flags a server starts with are a third), or the next author finding this
file and knowing the split is the first move rather than a surprise.

## Trail

- 2026-08-26: opened by the close of
  [R-460](460-the-reasoning-off-pair-is-spelled-in-three-places.md), which added the entry that
  brought the file to two lines under the cap.
