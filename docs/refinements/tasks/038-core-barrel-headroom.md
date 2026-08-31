# Headroom in `cortex_core/__init__.py`

**Status:** landed 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The barrel sat
at exactly the cap, so the *next* public core name broke the line-cap gate for whatever
unrelated change added it. None of the three options this entry listed was taken, because each
treated the 151-name public surface as the cost when the surface was never the problem: the
file spent **two** lines per name, one to import it and one to restate it in `__all__`.
Re-export is now declared with the typing spec's redundant-alias form (`X as X`), which pyright
honors identically and which says it once, so the same 151 names cost 151 lines and a new one
costs a line instead of two. No consumer changed (every name still imports from `cortex_core`,
so the package-level convention stands), no export was pruned, and no sub-barrel was
introduced. Two things the implementation found: ruff **exempts `__init__.py` from PLC0414**
(useless-import-alias) precisely because the redundant alias is the re-export convention there,
so `select = ["ALL"]` needed no new ignore; and nothing in the tree read `cortex_core.__all__`
(only `cortex_seam`'s own facade test reads its package's list), so dropping it broke no
contract. Verified clean: ruff, ruff format, pyright strict, and the full brain suite at 100%.

## Trail

- 2026-07-14: The barrel's headroom returned, 300 lines to 162.
- 2026-08-06: The barrel filled again, at about 290 public names and exactly 300 lines, and came
  off the line cap the same day, split into area sub-barrels under `cortex_core._surface` with
  every call site unmoved. The index's repo-gates row recorded that, and the entry carrying it in
  full is [the cortex_core barrel at its 300-line cap](015-core-barrel-line-cap.md), which names
  this entry's economy, halving the cost of a name from two lines to one by the redundant-alias
  re-export form, as the one it found spent. So the body above, where no sub-barrel was
  introduced, is the account of 2026-07-14 rather than of the tree after that split.
