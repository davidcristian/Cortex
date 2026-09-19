# Nothing notices an image declaring a volume no compose file mounts

**Status:** done 2026-08-25
**Area:** repo-checks
**Origin:** [ADR-0057](../../adr/ADR-0057-imap-probe-server.md)

A `VOLUME` in an image takes effect whether or not a compose file asked for it: a container with
nothing mounted at such a path gets an anonymous volume, seeded from the image's copy of the
directory, and `docker compose down` without `--volumes` leaves it on the host under a name nobody
chose. The probe's image declares two, `/srv/mail` and `/etc/dovecot`, and both were found by
reading `docker image inspect` by hand, months of runs apart, each after the leak had been
happening on every start. Nothing in this repo asks the question. A new version of the fixed image,
or any new image in any compose file here, can add a third, and the only symptom is
`docker volume ls` growing.

Where such a check can live is the hard part. `bindcheck.py` and `defaultcheck.py` read compose
files as text and run in CI, which has no docker and no images, so the question is unanswerable
there. The one thing in this repo that already talks to docker about a container is the probe's own
live suite, which is `integration`-marked and runs only when somebody measures.

## History

- 2026-08-24: filed by the close of
  [R-424](424-every-probe-run-leaves-an-anonymous-volume.md), which mounted the second of the two
  paths the probe's image declares and left the general question unasked.
- 2026-08-25: closed. The entry was right that nothing asked the question and wrong about where the
  answer would be interesting. Both of dovecot's declarations are covered, so the probe stack is
  clean. Surveying every image any compose file here names, which nobody had done, found a second
  offender that had been leaking the whole time: `pg-backup` in
  `docker/docker-compose.memory.yml` runs the same `pgvector/pgvector:pg16` image as the server,
  which declares `/var/lib/postgresql/data`, and mounts only its dump directory and its script. It
  holds no database of its own, dumping over the network with the image's entrypoint overridden, so
  docker was seeding a fresh anonymous volume from an empty data directory on every start of the
  memory stack. Reproduced at container level before the fix and confirmed gone after it, with a
  tmpfs at the declared path, the same remedy the probe fixture uses. Both of the entry's proposed
  shapes were passed over, the probe-suite assertion and a recipe beside it, for one reason: each
  only ever asks about a container somebody is already running, and the leak found here was in a
  stack the probe's suite never starts. The wide version the entry thought impossible is buildable
  by recording what docker says rather than asking it: `scripts/volumecheck.py` reads
  `scripts/imagevolumes.py`, eight measured rows, against what `scripts/composeservices.py` reads
  out of all ten compose files, and `just image-volumes` recomputes the record from a real daemon.
  Nineteen mutations over the `scripts` pytest suite of 1008 tests, seventeen expected to fail and
  two expected to pass, all as designed; the first pass was eighteen of nineteen, the miss a
  fixture fragment named for a recorded row, and that test is now the only thing covering its
  guard. Where such a check may live, and why it does not become a second recipe outside
  `just check`, is answered once in ADR-0067 decision 1. One residue filed: a mutable tag
  republished under the same name can change what it declares while the recorded answer, and every
  check here, stay exactly as they were
  ([R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md)).
