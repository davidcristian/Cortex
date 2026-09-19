# A compose bind default creating a directory in the tree

**Status:** done 2026-08-08
**Area:** repo-checks
**Origin:** [ADR-0063](../../adr/ADR-0063-compose-checks.md)

On 2026-08-06 `models/` was found root-owned and empty at the repo root, created that morning by a
container and matched by no ignore rule. `pgdata/`, where the pg-backup sidecar writes
`cortex.dump` (`CORTEX_DB_DIR`, [runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md)),
had the same exposure and had had it since that sidecar shipped. Both are ignored now, without a
leading slash so they match at any depth, because compose resolves a relative bind against the
project directory: the `just` recipes pass `--project-directory .` and a bare
`docker compose -f docker/docker-compose.memory.yml` does not, which puts the same two under
`docker/` instead.

A third default of the same form, `${CORTEX_TOOLS_ROOT:-./sandbox}`, was already ignored, which is
the point: the tree was clean because three people remembered, not because anything checked. Six
bind defaults existed then (four write `${CORTEX_MODELS_DIR:-./models}`, one
`${CORTEX_DB_DIR:-./pgdata}`, one the sandbox), every one written by root from inside a container,
and the files are GGUFs and database dumps rather than kilobytes, so this produces a
multi-gigabyte artifact one `git add -A` from the index.

Closed 2026-08-08 as `scripts/bindcheck.py`, a fourth cross-tree scan run unconditionally by
`just check` and by CI. The six defaults across five files reproduced exactly. Two parts of the
plan recorded here were wrong:

- The proposed rule, failing when a default is not matched by `.gitignore`, is false about the
  tree. Three more binds in `docker-compose.memory.yml` point at `./docker/postgres/init.sql`,
  `live-contract-db.sql` and `backup.sh`, which are inputs the repo ships and must never be
  ignored. The real rule has three cases: a bind source resolves outside the repo, or onto a path
  git tracks, or onto a path git ignores.
- Reading only `${VAR:-./path}` would miss a plain `source: ./cache` added later, which is exactly
  the next override this was waiting for. The scan reads bind mounts rather than variable syntax,
  and finds compose files by name anywhere under the root.

Two things the work turned up. Compose creates a directory, and a directory-only ignore pattern
(`models/`) does not match a path git cannot stat, so `check-ignore` must be asked with a trailing
slash; the scan flagged all six on its first run, which was the scan being wrong rather than the
tree. And the deliberate lack of a leading slash in `.gitignore` is now enforced: the scan
resolves every relative source against both project directories compose can pick, so an anchored
`/models/` is reported for leaving `docker/models` uncovered.

The tree was clean on the first correct run, so the scan was made to fail deliberately before
being relied on: a planted `docker/docker-compose.cache.yml` with `${CORTEX_CACHE_DIR:-./hfcache}`
produced two complaints and exit 1, and deleting the `models/` line from `.gitignore` produced
eight across four overrides. The reader is `scripts/composemounts.py`, split out because the two
together exceed the line cap; it raises rather than skips on any compose form it was not taught.

## History

- 2026-08-06: Opened when `models/` was found root-owned and empty at the repo root, created that
  morning by a container and matched by no ignore rule, with `pgdata/` in the same state since the
  pg-backup sidecar shipped. What made it an entry is the class rather than the two directories.
- 2026-08-08: Closed as `scripts/bindcheck.py`, run unconditionally by `just check` and by CI. The
  plan recorded here was wrong twice: three binds point at files the repo ships, so the rule has
  three cases, and the scan reads bind mounts rather than `${VAR:-./path}` syntax. The tree was
  clean on the first correct run, so the scan was made to fail deliberately, and the compose
  reader was split into `scripts/composemounts.py`.
