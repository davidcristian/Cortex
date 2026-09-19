# The repo map names two more trees in the readable form, and neither is checked

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

The repo map in [AGENTS.md](../../../AGENTS.md) is one fenced block, and six of its rows name what
a directory holds: `docs/`, `brain/packages/`, `body/crates/`, `scripts/`, `.github/` and
`docker/`. Only the `scripts/` row is checked, by a list over the modules on disk. The
`brain/packages/` row names every package in that workspace and the `body/crates/` row names every
crate in that one, both in the same columns, both in bare words, and both checked by nothing.

The cost is not the mechanism but the question of what a member is. A package under
`brain/packages/` is a directory, but the map's entry for it also names things that are not
packages, calling out where the subagent runner lives and which package hosts a service, so the
pattern has to exclude those. It also names one package that is not there, `shared` marked planned.
A crate under `body/crates/` is named in the map as `core`, `rpc`, `os_windows` and so on, which is
the directory name and not the Cargo package name, and the two differ for every one of the five:
`core` is the `body-core` package, `rpc` is `body-rpc`, and the three OS crates trade the
underscore for a hyphen.

What it became: two registry entries in `scripts/rosters.py`, two readers in
`scripts/rostermembers.py`, and one decision taken for both rows. A member is a name the row
follows with a parenthesised description, separated by a space or by the line break the map wraps
at. The borrowed-name allowance was not needed, because the form answers the question it was
written for: the row names a package while describing something else twice, and both names it
borrows are members anyway, so the comparison is over sets.

That decision settles the two cases this entry said had to be decided. `shared` is written
`(planned) shared`, the marker in front of the name and nothing behind it, so the planned row is
not read as a member; a planned row rewritten like a present one would be reported as a package the
tree does not have. And what is read is the directory and never the package name a manifest
declares: the crate divergence is five of five, so a reader over manifests would report every crate
as one the map does not name.

One line of the map moved to meet that decision, and it is this close's only source edit. The
crates row wrote its two stub crates as `os_linux/os_macos (cfg-gated stubs)`, which names the
first for a reader and neither for a rule, only the second being followed by a description. It now
reads `os_linux (cfg-gated stub) + os_macos (cfg-gated stub)`.

## History

- 2026-08-26: opened by the close of
  [R-449](449-the-repo-map-names-every-gate-module-unheld.md), which made the reader take a bare
  word inside a bounded passage and used that on one of the map's three name lists. Recorded as a
  limit ADR-0044 leaves open.
- 2026-09-09: trigger checked and not fired, and the count repaired. `brain/packages/` still names
  all eleven packages on disk plus a planned one, and `body/crates/` still names all five crates.
  What was wrong is the arithmetic: the entry said the block describes four trees and names the
  members of three, where six of its rows name what a directory holds. The crate-name divergence is
  also wider than the one case quoted.
- 2026-09-09: two of the four unchecked rows had already come apart, which is why this entry no
  longer says nothing is wrong today. `docs/` did not name `design/`, which holds the overlay's
  visual language, and `docker/` did not name `docker-compose.imap-probe.yml` or the `dovecot/`
  configuration beside it, all three tracked. Both rows were corrected in the same review.
- 2026-09-12: trigger checked and not fired, and the divergence count repaired again. The eleven
  directories under `brain/packages/` are the eleven the map names, `body_client`, `core`, `email`,
  `embedding`, `inference`, `memory`, `model_manager`, `orchestrator`, `seam`, `session` and
  `tools`, with `shared` named as planned and absent; the five under `body/crates/` are the five it
  names. The crate divergence is not three of five but five of five, read off each `Cargo.toml`:
  `body-core`, `body-rpc`, `os-linux`, `os-macos` and `os-windows`.
- 2026-09-12: the count of unchecked listings has not moved, and the reason is worth recording.
  `scripts/markdownfences.py` was added and `scripts/` now has 73 modules where it had 68, so the
  one row of the six that is checked gained a name in the same commit that added the module,
  because the list over it fails otherwise. The map was edited because a check demanded it, which
  is the clearest evidence yet of what the other two rows lack.
