# Every probe run leaves an anonymous volume behind, against its own promise

**Status:** landed 2026-08-24
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-24 by the close of
[R-390](390-the-probes-mail-root-is-spelled-in-three-files.md), which measured what the probe's
image does with the two paths it declares volumes at.

`dovecot/dovecot:2.3.21` declares `VOLUME /etc/dovecot` and `VOLUME /srv/mail`. The mail root is
covered: `docker/docker-compose.imap-probe.yml` mounts a tmpfs there, and the entrypoint now
refuses to start if that mount is missing, so nothing is written to a volume under it. The
configuration directory is not. The compose file binds one file inside it,
`/etc/dovecot/dovecot.conf`, which leaves the directory itself to docker, and docker fills it with
an anonymous volume for the life of the container. `just down-imap-probe` runs `docker compose
down` with no `--volumes`, which removes the container and the network and leaves that volume on
the host under a name nobody chose.

Measured on 2026-08-24: every container recreate made a fresh one, and `docker volume ls` was
holding dozens of anonymous volumes, five of them stamped with the previous day's probe session.
Each is a few kilobytes of the image's own configuration, so the cost is clutter rather than disk,
but the compose file's own comment says the fixture leaves nothing behind and that is not true
today.

**Why it was left.** The close it came out of was about the mail root, and this is a different
path with a different remedy. It also wants a decision rather than a keystroke: `down --volumes`
in the recipe is the obvious fix and it is a blunter instrument than it looks, since it would also
remove a named volume if this stack ever grew one, so the choice between it and mounting
`/etc/dovecot` in a way that leaves docker nothing to fill is worth making deliberately.

**What would close it.** Either add `--volumes` to `just down-imap-probe` (and say in the recipe
why a fixture stack may take the blunt instrument), or give the container an `/etc/dovecot` docker
has no reason to anonymise, for instance by binding the whole directory rather than the one file,
which the file's own comment currently argues against because the image's self-signed cert and key
live beside the conf. Then re-measure: bring the probe up and down and confirm `docker volume ls`
is unchanged across the cycle.

## Trail

- 2026-08-24: filed by the close of
  [R-390](390-the-probes-mail-root-is-spelled-in-three-files.md), which measured what the probe's
  image does with the two paths it declares volumes at and fixed only the mail root.
- 2026-08-24: landed. **Re-derived first, and one claim in this entry was wrong.** The leak itself
  held and was measured again with the recipes an operator runs: `docker volume ls` at 37 (34 of
  them anonymous), `up` then `down`, `docker volume ls` at 38, the container having carried
  `volume ... -> /etc/dovecot` beside its two binds. What did not hold is the reason the compose
  file gave for binding one file rather than the directory. `cert.pem` and `key.pem` are not files
  beside the conf in that image; they are symlinks into `/etc/ssl`, which nothing declares a volume
  at, so the argument against covering the directory was an argument about two symlinks.
  **`--volumes` on the down recipe is declined**, being a sweep after a well formed shutdown rather
  than a fixture that makes nothing to sweep, a rule about a future named volume written as a flag,
  and a promise the compose file makes resting on a recipe instead of on the stack. **The
  configuration directory is a tmpfs**, aliased from an anchor beside the mail root's and handed
  over as `CORTEX_IMAP_PROBE_CONFIG_ROOT`, so the fixture ends with one rule about both of the
  paths its image declares. The conf is bound in at `/probe.conf` and copied onto that mount by the
  entrypoint rather than bound straight at the path dovecot reads, which is what makes a moved
  anchor loud: dovecot's configuration directory is compiled in, so any other root is a server
  loading the image's own settings and seven red tests, where a bind would have left the suite
  green and the leak back. The conf names the files the symlinks name, and STARTTLS was verified
  over the wire rather than by reading the setting back. **Four planted mutations plus the
  pre-change and reverted rows**, over the probe's live suite, seven `integration`-marked tests
  that never run in CI, tabled in the configuration-directory addendum; the volume set was read
  before and after every cycle and ends where it started, at 37. One residue filed: nothing here
  notices an image declaring a volume no compose file mounts, which is how both halves of this were
  found by hand ([R-425](425-nothing-notices-an-image-volume-nobody-mounts.md)).
