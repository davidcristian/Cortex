# Readings: a Postgres data directory on the Windows drive

What Postgres does when its data directory is a bind mount onto a Windows drive under Docker
Desktop, against the named volume [ADR-0008](../adr/ADR-0008-memory-v1.md) decision 7 keeps it in.
Cited by that ADR and by [the memory runbook](../runbooks/memory-pgvector.md#export-and-restore).

## The two data directories side by side

**2026-10-07.** Docker Desktop's daemon, reached from a WSL shell through its WSL integration, ran
two `pgvector/pgvector:pg16` servers one after the other, each on CPUs 12 to 23 and with the
memory override's `cortex` user and database. One had `/var/lib/postgresql/data` bound to an empty
folder on a Windows drive through WSL's automatic drvfs mount; the other had a fresh named volume.
Inside the container the bind read as a `9p` mount with `aname=drvfs` and `metadata`. Docker
Desktop's VM mounts each Windows drive itself, also as `9p` drvfs with `metadata` (read from the
VM's `/proc/mounts`). A source given as a Windows path from PowerShell was not run and is assumed
to use that mount. A share mounted without `metadata` was not tried.

- **Ownership.** initdb's "fixing permissions on existing directory" step passed, and the data
  directory read as owned by `postgres` with mode 700 inside the container. The WSL user who
  created the folder could no longer list it.
- **It serves and survives a restart.** `CREATE EXTENSION vector` and a 1,000-row `vector(3)`
  table worked, and after `docker restart` the server read both that table and pgbench's
  1,000,000 rows back.
- **Bulk writes are slow.** The first start, initdb included, took about 6 times as long as on
  the named volume (1 s polling), and `pgbench -i -s 10` took 13 times as long.
- **Commits are not.** `pgbench -c 4 -j 2 -T 30`, which commits after every transaction, read
  1.35 and 1.06 times the named volume's rate in two runs; the volume's low first run came
  straight after its bulk load.
- **Syncs.** `pg_test_fsync -s 2` read `fdatasync`, Postgres's default `wal_sync_method` on Linux,
  at 0.87 of the named volume's rate, and `open_datasync` at about 10 times it. No reading here
  says whether a sync on the drive reaches the disk.

Method: `docker run -d --cpuset-cpus 12-23 -e POSTGRES_USER=cortex -e POSTGRES_PASSWORD=cortex
-e POSTGRES_DB=cortex -v <folder or volume>:/var/lib/postgresql/data pgvector/pgvector:pg16`,
then `pgbench` and `/usr/lib/postgresql/16/bin/pg_test_fsync` through `docker exec`; logs in
`measurements/pgdata-windows-drive-2026-10-07/`.
