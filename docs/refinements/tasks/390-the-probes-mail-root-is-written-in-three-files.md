# The probe's mail root is written in three files and nothing can compare them

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0057](../../adr/ADR-0057-imap-probe-server.md)

`/srv/mail` is written in `docker/dovecot/probe-mailboxes.sh` (twice, inside the account's home),
in `docker/dovecot/probe.conf` (twice, as the static userdb's `home=` and as `mail_home`) and in
`docker/docker-compose.imap-probe.yml` (once, as the tmpfs that makes the store throwaway). All
three must agree. Change the conf's alone and dovecot resolves a home nothing built, which fails
all six live tests at once. Change the tmpfs alone and nothing reports anything: the fixture still
works and no longer starts empty every time, which is the property its own comment claims for it.

No file declares it. `crosscheck.py` compares a declaration against the places restating it, and
`registry_fault` raises on an entry with no declaration, so both options are closed: there is
nothing to read, and adding a constant to a suite that has no use for the value would mean
declaring it only to satisfy the check. The account's own match uses `/srv/mail/{value}`, so the
prefix is covered in the script as fixed text and in neither of the other two files.

## History

- 2026-08-23: filed by the close of [R-384](384-the-probes-account-name-is-written-in-two-places.md), which
  registered the account name written under this root and recorded that the root above it has no
  declaration a scan could read.
- 2026-08-24: closed. The Origin line was wrong and is corrected: it named the constant scan's
  decision record, which is where the gap was written down, but the fixture belongs to the email
  record, now [ADR-0057](../../adr/ADR-0057-imap-probe-server.md) decision 7. The count was
  checked again and held, five occurrences across the three files above, none of them moved, and
  the live suite has grown from six tests to seven. Dovecot does take the path from the
  environment, measured against `dovecot/dovecot:2.3.21` in three containers rather than argued:
  `$ENV:NAME` is not expanded at all, `%{env:NAME}` is expanded and comes out empty unless the
  name is on `import_environment`, and with that line the account's home resolved to the handed-in
  root. So the root is written once, as a YAML anchor in the compose file, aliased into the tmpfs
  and into `CORTEX_IMAP_PROBE_MAIL_ROOT`, which the script and the conf both read. An anchor
  rather than a `${NAME:-default}` substitution, which would repeat the default once per use and
  would let a variable in an operator's shell move the fixture. One of the five occurrences was
  dead: `mail_home` is only ever the fallback for a userdb that answers with no home, and this one
  always answers with a home, so changing it alone did nothing and it is removed. The silent
  failure now reports: the entrypoint checks that the mail root really is a tmpfs before it builds
  anything, which also covers what the image does with that path, since it declares a volume there
  and docker fills an unmounted one with an anonymous volume that outlives the container. Six
  planted changes over the probe's live suite each failed as designed. The registry gained no row
  and `crosscheck.py`'s subject did not move: a value with one place is not a coupling, and the
  second option this entry offered, a registry over restating places only, is declined rather than
  deferred. One residue filed: the image declares `/etc/dovecot` a volume too, and the compose
  file binds one file inside it, so every run leaves an anonymous volume behind
  ([R-424](424-every-probe-run-leaves-an-anonymous-volume.md)).
