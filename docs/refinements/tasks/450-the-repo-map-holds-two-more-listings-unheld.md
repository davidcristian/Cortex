# The repo map names two more trees in the shape now readable, and neither is held

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-12
**Trigger:** a crate is added under `body/crates/` or a package under `brain/packages/` and the
repo map keeps describing the workspace that existed before it, which is the drift the same map's
`scripts/` row is held against by a roster.

Opened 2026-08-26 by the close of
[R-449](449-the-repo-map-names-every-gate-module-unheld.md), which made the roster reader take a
bare word inside a bounded passage and spent that on one entry of the repo map.

The repo map in [AGENTS.md](../../../AGENTS.md) is one fenced block, and six of its rows name what
a directory holds: `docs/`, `brain/packages/`, `body/crates/`, `scripts/`, `.github/` and
`docker/`. Only the `scripts/` row is held, by a roster over the modules on disk. The
`brain/packages/` row names every package in that workspace and the `body/crates/` row names
every crate in that one, both in the same columns, both in bare words, and both held by nothing.

Nothing is wrong in those two rows today, and two of the other four had drifted before this was
checked, which is the same fault arriving where nobody was watching for it. What the close bought
is that the shape those two are written in is no
longer the obstacle: a bare roster over either would be one registry entry plus one reader, and
the reader is a directory listing in both cases.

**Why it was left.** The close was about `scripts/`, and the entry that opened it said in as many
words to check what the shape costs the other trees before spending it on them. The cost is not
the mechanism, it is the question of what a member is. A package under `brain/packages/` is a
directory, but the map's entry for it also names things that are not packages, calling out where
the subagent runner lives and which package hosts a service, so the pattern that finds a name has
to exclude those. It also names one package that is not there, `shared` marked planned, so the
reader has to take a side on the planned row too. A crate under `body/crates/` is named in the map
as `core`, `rpc`, `os_windows` and so on, which is the directory name and not the Cargo package
name, and the two differ for **every one of the five**: `core` is the `body-core` package, `rpc` is
`body-rpc`, and the three OS crates trade the underscore for a hyphen, `os_windows` being
`os-windows`. So the reader has to pick a side and say why.

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
- 2026-09-09: trigger checked and not fired, and the count repaired. `brain/packages/` still names
  all eleven packages on disk plus a planned one, and `body/crates/` still names all five crates,
  so no crate or package has been added under a map that describes the workspace before it. What
  was wrong is the arithmetic: the entry said the block describes four trees and names the members
  of three, where six of its rows name what a directory holds, `docs/`, `brain/packages/`,
  `body/crates/`, `scripts/`, `.github/` and `docker/`. The crate-name divergence is also wider
  than the one case quoted, three of the five directory names differing from the Cargo package
  name rather than `os_windows` alone.
- 2026-09-09: two of the four unheld rows had already drifted, which is why this entry no longer
  says nothing is wrong today. `docs/` did not name `design/`, which holds the overlay's visual
  language, and `docker/` did not name `docker-compose.imap-probe.yml` or the `dovecot/`
  configuration beside it, all three tracked. Both rows were corrected in the same sweep, so the
  drift this entry predicts for the two rows it is about has already happened twice in rows it
  does not cover.
- 2026-09-12: trigger checked and not fired, and the divergence count repaired again. The eleven
  directories under `brain/packages/` are the eleven the map names, `body_client`, `core`, `email`,
  `embedding`, `inference`, `memory`, `model_manager`, `orchestrator`, `seam`, `session` and
  `tools`, with `shared` named as planned and absent; the five under `body/crates/` are the five it
  names. The crate divergence is not three of five but five of five, read off each
  `Cargo.toml`: `body-core`, `body-rpc`, `os-linux`, `os-macos` and `os-windows`, so a reader over
  that row cannot compare directory names to package names anywhere.
- 2026-09-12: the count of unheld listings has not moved, and the reason is worth recording.
  `scripts/markdownfences.py` was added earlier today and `scripts/` now holds 73 modules where it
  held 68, so the one row of the six that is held gained a name in the same commit that added the
  module, because the roster over it fails otherwise. The module that arrived landed in the held
  row, so the two rows this entry is about are still two, and the commit that added it is the
  clearest evidence yet of what those two lack: the map was edited because a gate demanded it.
