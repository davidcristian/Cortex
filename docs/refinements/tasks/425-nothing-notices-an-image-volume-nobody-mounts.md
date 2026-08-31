# Nothing notices an image declaring a volume no compose file mounts

**Status:** landed 2026-08-25
**Area:** repo-gates
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-24 by the close of
[R-424](424-every-probe-run-leaves-an-anonymous-volume.md), which mounted the second of the two
paths `dovecot/dovecot:2.3.21` declares a volume at.

A `VOLUME` in an image is a promise docker keeps whether or not a compose file asked for it: a
container with nothing mounted at such a path gets an anonymous volume, seeded from the image's
copy of the directory, and `docker compose down` without `--volumes` leaves it on the host under a
name nobody chose. The probe's image declares two, `/srv/mail` and `/etc/dovecot`, and both were
found by reading `docker image inspect` by hand, months of runs apart, each after the leak had
already been happening on every start. Nothing in this repo asks the question. A bump of the
pinned image, or any new image in any compose file here, can add a third and the only symptom is
`docker volume ls` growing.

**Why it was left.** It is a different subject from the leak it came out of, and it needs a
decision about where such a check can even live. `bindcheck.py` and `defaultcheck.py` read compose
files as text and run in CI, which has no docker and no images, so the question is unaskable
there: the answer is in a registry an image pull would have to fetch. The one thing in this repo
that already talks to docker about a container is the probe's own live suite, which is
`integration`-marked, excluded from the coverage gate, and runs only when somebody measures.

**What would close it.** The cheapest honest shape is probably an assertion in the probe's live
suite (`brain/packages/email/tests/test_imap_probe_live.py`): ask docker for the running
container's mounts and fail when any of them is an anonymous volume, which needs no image
inspection at all and catches a new declared volume the first time anyone measures. It also puts
a docker call into a suite that otherwise only speaks IMAP, so the alternative worth weighing is a
`just` recipe beside `email-folder-probe` that does the same thing and stays out of the tests. The
wider version, every image in every compose file here checked against what that file mounts, is a
scan that has to pull images and therefore cannot be part of `just check`; decide whether it is
worth having at all before building it.

## Trail

- 2026-08-24: filed by the close of
  [R-424](424-every-probe-run-leaves-an-anonymous-volume.md), which mounted the second of the two
  paths the probe's image declares and left the general question unasked.
- 2026-08-25: landed, and **the entry was right that nothing asked the question and wrong about
  where the answer would be interesting.** Both of dovecot's declarations are indeed covered
  today, so the probe stack is clean. Surveying every image any compose file here names, which
  nobody had done, found a second offender that had been leaking the whole time: `pg-backup` in
  `docker/docker-compose.memory.yml` runs the same `pgvector/pgvector:pg16` image as the server,
  which declares `/var/lib/postgresql/data`, and mounts only its dump directory and its script.
  It holds no database of its own, dumping over the network with the image's entrypoint
  overridden, so docker was seeding a fresh anonymous volume from an empty data directory on
  every start of the memory stack. Reproduced at container level before the fix and confirmed
  gone after it, with a tmpfs at the declared path, the same remedy the probe fixture uses.
  **Both of the entry's proposed shapes were passed over**, the probe-suite assertion and a
  recipe beside it, for one reason: each only ever asks about a container somebody is already
  running, and the leak found today was in a stack the probe's suite never starts. The wide
  version the entry thought impossible turns out to be buildable after all, by recording what
  docker says rather than asking it: `scripts/volumecheck.py` reads `scripts/imagevolumes.py`,
  eight measured rows, against what `scripts/composeservices.py` reads out of all ten compose
  files, and `just image-volumes` re-derives the record from a real daemon. **Nineteen mutations
  over the `scripts` pytest suite, 1008 tests, seventeen expected red and two expected green, all
  as designed**, tabled in the ADR-0022 addendum; the first pass was eighteen of nineteen and the
  miss is recorded there rather than smoothed over. Where such a check may live, and why it does
  not become a second recipe outside `just check`, is answered once in the ADR-0011 addendum on
  evidence out of the gate's reach, which both this and its sibling deferral point at. One
  residue filed: a mutable tag republished under the same name can change what it declares while
  the recorded answer, and every gate here, stay exactly as they were
  ([R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md)).
