# The subagent couplings part sits two lines under the line cap

**Status:** landed 2026-08-26
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

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
- 2026-08-26: landed as the
  [ADR-0029 addendum on splitting the subagent part](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-26-the-subagent-part-splits-on-the-line-between-a-run-and-its-container),
  taken on its own rather than inside the next coupling. The seam is the first of the three this
  entry named and it was already written down twice: `registry.py` describes
  `subagentcouplings` as the tier's admission budgets against the container limits that are their
  hard twins, which said nothing about the four bounds one delegated run stands between, and those
  four are the only entries in the file whose far sides are all documents, no stack under
  `docker/` spelling one of them. They are now `scripts/boundscouplings.py` at 175 lines, the
  eleventh part, leaving `scripts/subagentcouplings.py` at 163. The flag pair stayed with the
  budgets, being a property of the servers that stack starts. **No mutation table was owed and
  none was written**: the entries moved verbatim into the position they already occupied, so
  `crosscheck.CONSTANTS` reads the same 73 entries in the same order and prints the same shape,
  measured on both sides and diffed label by label. Three of the four listings that name a part
  were held, and `rostercheck.py` named all three misses in one run rather than leaving them to a
  hand search; the fourth, `registry.py`'s own docstring, is held by the constant suite. The two
  hand tallies beside those listings were updated by hand, which is the residue
  [R-449](449-the-repo-map-names-every-gate-module-unheld.md) already carries.
