# The probe's mail root is spelled in three files and nothing can hold them together

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** the first edit that moves `/srv/mail`, or a fourth place spelling it, meaning somebody
changing the probe's mail store and having to find the other two by reading.

Opened 2026-08-23 by the close of
[R-384](384-the-probe-account-is-spelled-twice.md), which registered the account under that root
and found the root itself unregistrable.

`/srv/mail` is written in `docker/dovecot/probe-mailboxes.sh` (twice, inside the account's home),
in `docker/dovecot/probe.conf` (twice, as the static userdb's `home=` and as `mail_home`) and in
`docker/docker-compose.imap-probe.yml` (once, as the tmpfs that makes the store throwaway). All
three must agree. Move the conf's alone and dovecot resolves a home nothing built, which is the
same total failure a renamed account produces, all six live tests going red at once. Move the
tmpfs alone and the store quietly stops being a tmpfs: the fixture still works and no longer starts
empty every time, which is the property its own comment claims for it.

**Why it was left.** No tree declares it. `crosscheck.py` compares a declaration against the places
restating it, and `registry_fault` refuses an entry with no site, so the two honest options are
both closed: there is nothing to read, and inventing a constant in a suite that has no use for the
value would be the gate editing the contract it watches. The account's own mention carries
`/srv/mail/{value}`, so the prefix is held in the script as part of that template's shape and in
neither of the other two files. That is where it stands today.

**What would close it.** The shape is the one the compose defaults were in before
[R-355](355-one-variable-several-defaults-no-declaration.md): a value several places must share
with no declaration anywhere, which was answered with a gate of its own rather than by stretching
the registry. The cheapest honest answer here may be smaller than a gate. A path the fixture files
share could be declared once in the compose file and passed into the container as an environment
variable the script and the conf both read, which turns three spellings into one and needs no scan
at all; whether dovecot's config can take it from the environment is the first thing to check.
Failing that, the question is whether a registry can hold a coupling whose places are all far
sides, which is a change to `crosscheck.py`'s stated subject and wants an ADR rather than a row.

## Trail

- 2026-08-23: filed by the close of [R-384](384-the-probe-account-is-spelled-twice.md), which
  registered the account name spelled under this root and recorded that the root above it has no
  declaration a scan could read.
