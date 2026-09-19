# Every probe run leaves an anonymous volume behind, against its own promise

**Status:** done 2026-08-24
**Area:** email-confirmer
**Origin:** [ADR-0057](../../adr/ADR-0057-imap-probe-server.md)

`dovecot/dovecot:2.3.21` declares `VOLUME /etc/dovecot` and `VOLUME /srv/mail`. The mail root is
covered: `docker/docker-compose.imap-probe.yml` mounts a tmpfs there, and the entrypoint exits if
that mount is missing. The configuration directory is not. The compose file binds one file inside
it, `/etc/dovecot/dovecot.conf`, which leaves the directory itself to docker, and docker fills it
with an anonymous volume for the life of the container. `just down-imap-probe` runs
`docker compose down` with no `--volumes`, so that volume stays on the host under a name nobody
chose.

Measured on 2026-08-24: every container recreate made a fresh one, and `docker volume ls` held
dozens of anonymous volumes, five of them from the previous day's probe session. Each is a few
kilobytes, so the cost is clutter rather than disk, but the compose file's own comment says the
fixture leaves nothing behind.

`down --volumes` in the recipe is the obvious fix and is blunter than it looks, since it would also
remove a named volume if this stack ever grew one. The alternative is to give the container an
`/etc/dovecot` docker has no reason to fill, for instance by binding the whole directory.

## History

- 2026-08-24: filed by the close of
  [R-390](390-the-probes-mail-root-is-spelled-in-three-files.md), which measured what the probe's
  image does with the two paths it declares volumes at and fixed only the mail root.
- 2026-08-24: closed. One claim in this entry was wrong. The leak held and was measured again with
  the recipes an operator runs: `docker volume ls` at 37 (34 of them anonymous), `up` then `down`,
  `docker volume ls` at 38, the container having had `volume ... -> /etc/dovecot` beside its two
  binds. What did not hold is the reason the compose file gave for binding one file rather than the
  directory. `cert.pem` and `key.pem` are not files beside the conf in that image; they are
  symlinks into `/etc/ssl`, which nothing declares a volume at. `--volumes` on the down recipe is
  declined, being a cleanup after a well formed shutdown rather than a fixture that makes nothing
  to clean up, a rule about a future named volume written as a flag, and a promise the compose file
  makes resting on a recipe instead of on the stack. The configuration directory is now a tmpfs,
  aliased from an anchor beside the mail root's and handed over as
  `CORTEX_IMAP_PROBE_CONFIG_ROOT`, so the fixture ends with one rule about both of the paths its
  image declares. The conf is bound in at `/probe.conf` and copied onto that mount by the
  entrypoint rather than bound straight at the path dovecot reads, which is what makes a moved
  anchor visible: dovecot's configuration directory is compiled in, so any other root is a server
  loading the image's own settings and seven failing tests, where a bind would have left the suite
  passing and the leak in place. The conf names the files the symlinks name, and STARTTLS was
  verified over the wire rather than by reading the setting back. Four planted mutations plus the
  pre-change and reverted rows, over the probe's live suite of seven `integration`-marked tests
  that never run in CI, each failing as designed; the volume set was read before and after every
  cycle and ends where it started, at 37. One residue filed: nothing here reports an image
  declaring a volume no compose file mounts, which is how both halves of this were found by hand
  ([R-425](425-nothing-notices-an-image-volume-nobody-mounts.md)).
