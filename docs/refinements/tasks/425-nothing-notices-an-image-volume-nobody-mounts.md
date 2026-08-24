# Nothing notices an image declaring a volume no compose file mounts

**Status:** open, actionable
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

**Why it was left.** It is a different subject from the leak it came out of, and it wants a
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
