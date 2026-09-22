# The subagent couplings part sits two lines under the line cap

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The cap is 300 lines and `scripts/subagentcouplings.py` was at 298, so the next entry written into
it would fail the line cap. That is the check working, and it is also a trap for whoever writes
that entry: they would be splitting a registry part in the middle of recording a coupling.

Splitting a part is not free. `registry.py` describes every part in prose that is compared with the
directory and with the order the tuple joins them in, the module contract names the same set, and
the repo map names it again, so a split touches four documents and a checked list.

## History

- 2026-08-26: opened by the close of
  [R-460](460-the-subagent-tiers-reasoning-off-flags-are-written-in-three-files.md), whose entry took the file from
  256 lines to 298.
- 2026-08-26: closed as the subagent part split of
  [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md), taken on its own rather than
  inside the next coupling. The dividing line was already written down twice: `registry.py`
  describes `subagentcouplings` as the tier's admission budgets against the container limits, which
  says nothing about the four bounds one delegated run stands between, and those four are the only
  entries in the file whose far sides are all documents. They are now `scripts/boundscouplings.py`
  at 175 lines, the eleventh part, leaving `scripts/subagentcouplings.py` at 163. The flag pair
  stayed with the budgets, being a property of the servers that stack starts. No mutation table was
  owed and none was written: the entries moved unchanged into the position they already occupied,
  so `crosscheck.CONSTANTS` reads the same 73 entries in the same order, measured on both sides and
  diffed label by label. Three of the four listings that name a part are checked, and
  `rostercheck.py` named all three misses in one run; the fourth, `registry.py`'s own docstring, is
  checked by the constant suite. The two hand tallies beside those listings were updated by hand,
  which is the residue [R-449](449-the-repo-map-names-every-check-module-in-an-unseen-block.md) records.
