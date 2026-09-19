# Headroom in `cortex_core/__init__.py`

**Status:** done 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The barrel sat at exactly the 300-line cap, so the next public core name would break it for
whatever unrelated change added it. None of the three options recorded here was taken, because
each treated the 151-name public surface as the cost when the surface was never the problem: the
file spent two lines per name, one to import it and one to repeat it in `__all__`. Re-export is
now declared with the typing specification's redundant-alias form (`X as X`), which pyright treats
identically and which says the name once, so the same 151 names cost 151 lines and a new one costs
one line instead of two. No consumer changed, no export was removed, and no sub-barrel was added.

Two things the work found: ruff exempts `__init__.py` from PLC0414 (useless-import-alias),
precisely because the redundant alias is the re-export convention there, so `select = ["ALL"]`
needed no new ignore; and nothing in the tree read `cortex_core.__all__`, only `cortex_seam`'s own
facade test reading its own package's list, so dropping it broke no contract. Checked clean with
ruff, ruff format, pyright strict and the full brain suite at 100%.

## History

- 2026-07-14: The barrel's headroom returned, 300 lines to 162.
- 2026-08-06: The barrel filled again, at about 290 public names and exactly 300 lines, and came
  off the cap the same day, split into area sub-barrels under `cortex_core._surface` with every
  call site unmoved. The entry that records that is
  [R-015](015-core-barrel-line-cap.md), which names this entry's saving, one line per name instead
  of two, as the one it found spent. So the account above is of 2026-07-14 rather than of the tree
  after that split.
