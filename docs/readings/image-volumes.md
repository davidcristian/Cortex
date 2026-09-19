# Readings: what images declare, and how a build inherits it

How docker turns a declared `VOLUME` into an anonymous volume, and which declarations reach an image
built from a base. Cited by [ADR-0067](../adr/ADR-0067-image-volume-record.md), decisions 4 and 8 to
10. What each version-locked image declares today is not recorded here: `scripts/imagevolumes.py` is
that record, and `just image-volumes` recomputes it.

## A sidecar collecting a volume it never uses

**2026-08-25.** A container created with exactly `pg-backup`'s mounts at the time, the dump
directory and the script, from `pgvector/pgvector:pg16`:

```
$ id=$(docker create --network none -v "$PWD/docker/postgres/backup.sh:/backup.sh:ro" \
    -v "$PWD/pgdata:/backup" --entrypoint /bin/sh pgvector/pgvector:pg16 /backup.sh)
$ docker inspect "$id" --format '{{range .Mounts}}TYPE={{.Type}} DST={{.Destination}}
{{end}}'
TYPE=bind DST=/backup.sh
TYPE=bind DST=/backup
TYPE=volume DST=/var/lib/postgresql/data
```

The third mount is anonymous, seeded from the image's empty data directory, one per start.

## What a built image inherits

Taken against docker 29.7.2 with throwaway probe images, reading `Config.Volumes` through
`imagedrift.INSPECT_FORMAT` and `Config.OnBuild` beside it.

| Date | Base or stage | Child Dockerfile | Child declares |
| --- | --- | --- | --- |
| 2026-08-28 | base declares `/probe/base` | `FROM` it, nothing else | `/probe/base` |
| 2026-08-28 | a `FROM ... AS builder` stage declares `/probe/builder` | last stage stands elsewhere | nothing from the builder |
| 2026-08-29 | base declares `/probe/base` | declares `/probe/own` | both |
| 2026-08-29 | base holds only `ONBUILD VOLUME /probe/onbuild`, its own volumes empty | `FROM` it, nothing else | `/probe/onbuild`, and its own `Config.OnBuild` is `null` |
| 2026-08-30 | triggers `ONBUILD VOLUME /probe/onbuild`, the array form with two paths, `ONBUILD RUN true` | `FROM` it, nothing else | all three paths |

The same `ONBUILD` builds under `DOCKER_BUILDKIT=0` declare the same paths, so this is the builder
rather than one frontend. `VOLUME []` is refused by the builder, so no Dockerfile can shrink what it
inherits. Docker stores a trigger as the file wrote it (a lowercase `onbuild volume /probe/lower`
is stored lowercase and fires) and joins a continuation before storing it.

So the union of a Dockerfile's own declarations and its base's is the minimum the built image
declares: a base whose own row is empty can still make its children declare a path.

## How stale a built row can get

**2026-08-28.** On the development machine, `cortex-mcp-email` had a build from 2026-07-03 while
`python:3.12-slim-trixie` beside it had been republished on 2026-08-25: eight weeks in which that
row described an image no fresh build would produce. Both bases declared no volume and no trigger
that day, and all ten rows read `null` for `Config.OnBuild` on 2026-08-30.

Method: each probe is a two-line Dockerfile built and inspected by hand; `just image-volumes`
recomputes the real rows against a running daemon.
