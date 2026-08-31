# The probe's mail root is spelled in three files and nothing can hold them together

**Status:** landed 2026-08-24
**Area:** repo-gates
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-23 by the close of
[R-384](384-the-probe-account-is-spelled-twice.md), which registered the account under that root
and found the root itself unregistrable.

`/srv/mail` is written in `docker/dovecot/probe-mailboxes.sh` (twice, inside the account's home),
in `docker/dovecot/probe.conf` (twice, as the static userdb's `home=` and as `mail_home`) and in
`docker/docker-compose.imap-probe.yml` (once, as the tmpfs that makes the store throwaway). All
three must agree. Move the conf's alone and dovecot resolves a home nothing built, which is the
same total failure a renamed account produces, all six live tests failing at once. Move the
tmpfs alone and the store stops being a tmpfs without reporting anything: the fixture still works and no longer starts
empty every time, which is the property its own comment claims for it.

**Why it was left.** No tree declares it. `crosscheck.py` compares a declaration against the places
restating it, and `registry_fault` raises on an entry with no site, so the two honest options are
both closed: there is nothing to read, and inventing a constant in a suite that has no use for the
value would mean adding a declaration only to satisfy the gate. The account's own mention carries
`/srv/mail/{value}`, so the prefix is held in the script as fixed text inside that template and in
neither of the other two files. That is where it stands today.

**What would close it.** The shape is the one the compose defaults were in before
[R-355](355-one-variable-several-defaults-no-declaration.md): a value several places must share
with no declaration anywhere, which was answered with a gate of its own rather than by stretching
the registry. The cheapest honest answer here may be smaller than a gate. A path the fixture files
share could be declared once in the compose file and passed into the container as an environment
variable the script and the conf both read, which turns three spellings into one and needs no scan
at all; whether dovecot's config can take it from the environment is the first thing to check.
Failing that, the question is whether a registry can hold a coupling whose places are all far
sides, which is a change to `crosscheck.py`'s stated subject and needs an ADR rather than a row.

## Trail

- 2026-08-23: filed by the close of [R-384](384-the-probe-account-is-spelled-twice.md), which
  registered the account name spelled under this root and recorded that the root above it has no
  declaration a scan could read.
- 2026-08-24: landed. **The origin line was wrong and is corrected.** It named the constant scan's
  decision record, which is where the gap was written down; the fixture whose files spell the root
  belongs to the email record, and that is where the addendum went. **Re-derived first and the
  count held**, five spellings across the three files named above, none of them moved, and the
  live suite has grown from six tests to seven. **Dovecot does take the path from the environment**,
  measured against `dovecot/dovecot:2.3.21` in three containers rather than argued: `$ENV:NAME` is
  not expanded at all, `%{env:NAME}` is expanded and empties unless the name is on
  `import_environment`, and with that line the account's home resolved to the handed-in root. So
  the root is written once, as a YAML anchor in the compose file, aliased into the tmpfs and into
  `CORTEX_IMAP_PROBE_MAIL_ROOT`, which the script and the conf both read. An anchor rather than a
  `${NAME:-default}` substitution, which would spell the default once per use and would let a
  variable in an operator's shell move the fixture. **One of the five spellings was dead**:
  `mail_home` is only ever the fallback for a userdb that answers with no home, and this one always
  does, so misspelling it alone changed nothing and it is removed rather than carried forward.
  **The failure that reported nothing now reports**: the entrypoint checks that the mail root really is a tmpfs
  before it builds anything, which also covers what the image does with that path, since it
  declares a volume there and docker fills an unmounted one with an anonymous volume that outlives
  the container. Six planted mutations over the probe's live suite, tabled in the one-mail-root
  addendum. The registry gained no row and `crosscheck.py`'s subject did not move: a value with one
  place is not a coupling, and the second option this entry offered, a registry over far sides
  only, is declined rather than deferred. One residue filed: the image declares `/etc/dovecot` a
  volume too, and the compose file binds one file inside it, so every run leaves an anonymous
  volume behind ([R-424](424-every-probe-run-leaves-an-anonymous-volume.md)).
