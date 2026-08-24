# Every probe run leaves an anonymous volume behind, against its own promise

**Status:** open, actionable
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
