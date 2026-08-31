# A compose bind default landing in the tree

**Status:** landed 2026-08-08
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-06, when `models/` was found root-owned and
empty at the repo root, created that morning by a container and matched by no ignore rule;
`pgdata/`, where the pg-backup sidecar writes `cortex.dump` (`CORTEX_DB_DIR`,
[runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md)), carried the same exposure and had
carried it since that sidecar shipped. Both are ignored now, unanchored so they match at any
depth, because compose resolves a relative bind against the **project directory**: the `just`
recipes pass `--project-directory .` and a bare `docker compose -f
docker/docker-compose.memory.yml` does not, which puts the same two under `docker/` instead. A
third default of the same shape, `${CORTEX_TOOLS_ROOT:-./sandbox}`, was already ignored, and that
is the point rather than a reassurance: the tree is clean by three separate acts of remembering
and not by anything that checks. What is deferred is the check. Six bind defaults exist today
(four spell `${CORTEX_MODELS_DIR:-./models}`, one `${CORTEX_DB_DIR:-./pgdata}`, one the sandbox),
every one of them written by root from inside a container, and the artifacts are GGUFs and
database dumps rather than kilobytes, so what this class produces is a multi-gigabyte artifact one
`git add -A` from the index. The fix is a scan reading the `${VAR:-./path}` defaults out of
`docker/*.yml` and failing when one is not matched by `.gitignore`, which is `crosscheck.py`'s own
method of tying two files that must agree, and about the same size. The trigger is the next
override that adds a bind default, since a scan written today would guard a set of three that is
already correct.

**Landed 2026-08-08, ahead of its trigger, and the entry's own sketch of the fix was wrong in
two ways worth recording.** `scripts/bindcheck.py` is a fourth cross-tree scan beside the line
cap, the dash ban and the constant registry, run unconditionally by `just check` and by CI
([ADR-0026 bind addendum](../../adr/ADR-0026-prose-style-gates.md)). The six defaults across five
files reproduced exactly as written above. What did not survive contact was the rule: this entry
proposed "failing when one is not matched by `.gitignore`", and that rule is false about the
tree it would have gated. Three more binds in `docker-compose.memory.yml` point at
`./docker/postgres/init.sql`, `live-contract-db.sql` and `backup.sh`, which are inputs the repo
ships and must never be ignored, so the honest rule is a three-way one: a bind source resolves
**outside** the repo, or onto a path git **tracks**, or onto a path git **ignores**. The second
way it was wrong is narrower and matters more for the trigger: reading only `${VAR:-./path}`
would not read a plain `source: ./cache` added later, which is exactly the "next
override" this entry was waiting for. The scan reads bind mounts, not variable syntax, and finds
compose files by name anywhere under the root rather than by a `docker/*.yml` glob.
**Two things the writing turned up.** Compose materializes a **directory**, and a directory-only
ignore pattern (`models/`) does not match a path git cannot stat, so `check-ignore` has to be
asked with a trailing slash or the gate reports every one of these bare; that was found by the
scan flagging all six on its first run, which was the scan being wrong rather than the tree. And
the unanchored-on-purpose note in `.gitignore` is now enforced rather than remembered: the scan
resolves every relative source against both project directories compose can pick, so an anchored
`/models/` is reported for leaving `docker/models` uncovered.
**No pre-existing violation was found.** The tree was clean on the first correct run, which the
entry predicted ("a scan written today would guard a set of three that is already correct"), and
the value is entirely in the fourth case. It was therefore made to fail deliberately before being
trusted: a planted `docker/docker-compose.cache.yml` carrying `${CORTEX_CACHE_DIR:-./hfcache}`
drew two complaints and exit 1, and deleting the `models/` line from `.gitignore` drew eight
across four overrides; both returned to `bindcheck OK` on revert. The reader is
`scripts/composemounts.py`, split out because the two together are over the line cap, and it
raises rather than skips on every compose shape it was not taught, since a reader that skipped a
new override's one mount without reporting it is the same gate that cannot fail in a different
place.

## Trail

- 2026-08-06: Opened when `models/` was found root-owned and empty at the repo root, created that
  morning by a container and matched by no ignore rule, with `pgdata/` carrying the same exposure
  since the pg-backup sidecar shipped. The area went from six entries to seven, and what
  increments it is the class rather than the two directories: a third default of the same shape
  was already ignored, so the tree was clean by three separate acts of remembering rather than by
  anything that checks.
- 2026-08-08: Landed ahead of its trigger as `scripts/bindcheck.py`, a fourth cross-tree scan run
  unconditionally by `just check` and by CI. The entry's own sketch of the fix was wrong twice:
  three binds point at files the repo ships, so the honest rule is that a bind source resolves
  outside the repo, or onto a path git tracks, or onto one git ignores, and the scan reads bind
  mounts rather than `${VAR:-./path}` syntax, since a plain `source: ./cache` added later is the
  very case the trigger named. The tree was clean on the first correct run, so the gate was
  made to fail deliberately before being trusted, and the compose reader was split into
  `scripts/composemounts.py`.
