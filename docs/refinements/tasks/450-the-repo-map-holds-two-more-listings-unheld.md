# The repo map names two more trees in the shape now readable, and neither is held

**Status:** open, fix when it bites
**Trigger:** a crate is added under `body/crates/` or a package under `brain/packages/` and the
repo map keeps describing the workspace that existed before it, which is the drift the same map's
`scripts/` entry was just held against, four lines up.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-449](449-the-repo-map-names-every-gate-module-unheld.md), which made the roster reader take a
bare word inside a bounded passage and spent that on one entry of the repo map.

The repo map in [AGENTS.md](../../../AGENTS.md) describes four trees in one fenced block and names
the members of three of them. The `scripts/` entry is now a roster over the modules on disk. The
`brain/packages/` entry names every package in that workspace and the `body/crates/` entry names
every crate in that one, both in the same columns, both in bare words, and both held by nothing.

Nothing is wrong today. What the close bought is that the shape those two are written in is no
longer the obstacle: a bare roster over either would be one registry entry plus one reader, and
the reader is a directory listing in both cases.

**Why it was left.** The close was about `scripts/`, and the entry that opened it said in as many
words to check what the shape costs the other trees before spending it on them. The cost is not
the mechanism, it is the question of what a member is. A package under `brain/packages/` is a
directory, but the map's entry for it also names things that are not packages, calling out where
the subagent runner lives and which package hosts a service, so the pattern that finds a name has
to exclude those. A crate under `body/crates/` is named in the map as `core`, `rpc`,
`os_windows` and so on, which is the directory name and not the Cargo package name, and the two
differ (`os_windows` on disk is the `os-windows` package), so the reader has to pick a side and
say why.

**What would close it.** Two registry entries and one or two readers, plus a decision per tree
about what its map entry claims to be a complete list of. Read
[R-451](451-a-borrowed-name-cannot-be-told-from-a-claimed-one.md) first, since the `brain/`
entry's habit of naming a package while describing something else is exactly the shape the
borrowed-name allowance was written for and exactly the shape it cannot distinguish.

## Trail

- 2026-08-26: opened by the close of
  [R-449](449-the-repo-map-names-every-gate-module-unheld.md), which made the shape readable and
  spent it on one of the map's three name lists. Recorded under what the ADR-0029 addendum on
  holding that listing in halves defers.
