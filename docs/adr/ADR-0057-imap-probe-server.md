# ADR-0057: The IMAP probe server

**Status:** Accepted (2026-09-05)

## Context

The email reader classifies what an IMAP server answers
([ADR-0056](ADR-0056-email-reader-answers.md)): a refused `SELECT` is a folder correction only when
the answer proves the name missing, a flagged name is opened before it is dropped, and a declined
read is never reported as a message that is not there. The ProtonMail Bridge this repo talks to
cannot produce most of the cases those rules turn on. Every wrong name is refused in the same words,
every listed folder opens, and no read is ever declined, so a rule built on the Bridge alone would
rest on one server's English and on cases nobody had seen.

The probe is a second, real IMAP server this repo builds and can rebuild, holding a mailbox tree
made to produce each of those cases, so the rules are measured against two servers that disagree
about wording. Its measured answers are in
[docs/readings/imap-server-answers.md](../readings/imap-server-answers.md).

## Decision

1. **A version-locked Dovecot, run as a fixture and not a service.**
   [docker/docker-compose.imap-probe.yml](../../docker/docker-compose.imap-probe.yml) starts
   `dovecot/dovecot:2.3.21` with its ACL plugin, no password checked, and a loopback-only publish
   (`127.0.0.1:11143`), under its own project name and network; nothing in the brain stack points at
   it. It is started and stopped around a measurement: `just up-imap-probe`,
   `just email-folder-probe` (the live suite, `brain/packages/email/tests/test_imap_probe_live.py`),
   `just down-imap-probe`. The version is locked because the wordings the folder rules read were
   measured against one build; the tag's digest is recorded with the measurements, since a tag can
   be republished under an unchanged name. The measuring recipe asks docker where the server answers
   and falls back to the container's own address, because a Docker Desktop engine publishes onto the
   Windows host and a WSL distro reaches the bridge network instead.
2. **The tree holds one mailbox per case, and each name says what the server does with it.**
   [docker/dovecot/probe-mailboxes.sh](../../docker/dovecot/probe-mailboxes.sh) builds it on every
   start:

   | name | what it produces |
   | --- | --- |
   | `INBOX`, `Parent/Child` | ordinary mailboxes that open |
   | `Parent` | a `\Noselect` hierarchy node, refused as missing |
   | `Guarded` | listed, unflagged, and shut by an ACL of `owner l`: `NO [NOPERM]` |
   | `Ghost` | subscribed with no mailbox, so a subscribed listing flags it `\NonExistent` |
   | `Feigned`, `Feigned/Followed` | an unsubscribed parent with a subscribed child, which RFC 3501 section 6.3.9 has `LSUB` flag `\Noselect` though it opens |
   | `Sealed` | opens, and holds one message owned by root at mode 000, so its read is declined |

   The names form one family: participles for what the server does to the name (`Guarded`,
   `Feigned`, `Sealed`) beside nouns for what the name is (`Parent`, `Child`, `Ghost`); `Followed`
   is named for the subscription that causes its parent's flag. Alternatives considered: `Masked`
   and `Belied` for `Feigned`, `Withheld` and `Locked` for `Sealed` (the second reads as an ACL, the
   one thing it is not). The subscription file is written directly (`V<TAB>2`, an empty namespace
   line, one name per line), because `SUBSCRIBE Ghost` is refused.
3. **The fixture's names are tied to the live suite's constants** by
   [scripts/fixturecouplings.py](../../scripts/fixturecouplings.py): the account, each mailbox the
   suite reads by name, the subscription entries, and `SEALED_FOLDER` and `SEALED_UID` tied to the
   script's `doveadm save` and the file it shuts. A rename on one side alone fails `just check`
   rather than the next measurement.
4. **A declined read is a tagged `NO`.**
   [docker/dovecot/probe.conf](../../docker/dovecot/probe.conf) sets
   `imap_fetch_failure = no-after`, so the sealed message's FETCH answers `NO [SERVERBUG] ...` on a
   connection that stays open; that is the answer the contract's declined-read check needs and the
   Bridge cannot give. Dovecot's default, `disconnect-immediately`, answers the same fault with
   `* BYE FETCH failed...` and drops the connection; the unit suite scripts that sentence as
   `DROPPED_READ`, measured by hand twice, and no second service runs the default, since no
   classification reads its words (`_translated` wraps every library failure alike).
5. **The sealed message is saved through a server that is then stopped.** A dbox message exists only
   once an index names it, and `doveadm save` needs the auth socket a running server creates. So the
   entrypoint starts dovecot once on `127.0.0.1` (out of the publish's reach), waits for the socket,
   saves the message, shuts its file, runs `doveadm stop`, waits for the pid file to go, and then
   `exec`s the server the suite reaches. Both waits are bounded and name themselves in the log when
   they give up.
6. **Both paths the image declares as volumes are tmpfs mounts.** The image declares
   `VOLUME /srv/mail` and `VOLUME /etc/dovecot`, and docker fills a declared path nothing is mounted
   at with an anonymous volume that `down` leaves on the host. A tmpfs at each leaves docker nothing
   to fill and keeps the store empty on every start. The entrypoint checks both are really tmpfs
   before building anything and exits with one line naming which if not, so a fixture that stopped
   being throwaway will not start. `scripts/volumecheck.py` compares the compose file with the
   image's recorded declarations in `just check` ([ADR-0067](ADR-0067-image-volume-record.md)).
7. **Each root is written once, as a YAML anchor.** `x-mail-root: &mail-root "/srv/mail"` and
   `x-config-root: &config-root "/etc/dovecot"` are aliased into the tmpfs list and into
   `CORTEX_IMAP_PROBE_MAIL_ROOT` and `CORTEX_IMAP_PROBE_CONFIG_ROOT`, which the script reads under
   `set -u` and the conf reads as `home=%{env:CORTEX_IMAP_PROBE_MAIL_ROOT}/%Lu`. That expansion
   needs the name on `import_environment`, or it expands to nothing. An anchor rather than a
   `${VAR:-default}` substitution, because a substitution repeats the default at each use and reads
   the operator's shell, which could move a fixture whose value is that it never moves.
8. **The configuration is copied onto the tmpfs, not bound onto it.** The conf is bound at
   `/probe.conf` and the entrypoint copies it to `$CORTEX_IMAP_PROBE_CONFIG_ROOT/dovecot.conf`.
   Dovecot's configuration directory is compiled in, so with the copy a configuration root set to
   any other path leaves the server on the image's own settings (no ACL plugin) and the live suite
   failing; a bind would end up inside whatever docker made anonymous and stay passing. The image's
   `cert.pem` and `key.pem` are symlinks, so `ssl_cert` and `ssl_key` name the snakeoil files they
   point at.
9. **Live assertions read the attribute words they are about, never an exact flag tuple.** This
   server adds `\UnMarked` to a mailbox once something has searched it, and the contract searches
   every offered name, so an exact tuple passes on a fresh container and fails on the next run.

## Consequences

- The folder rules rest on two servers: the Bridge and this fixture agree on each fact and share no
  wording, and the tables in the measurement record are what the phrases and codes were read from.
- A bump of the image is visible to `just check` (`volumecheck` fails on an unrecorded reference),
  but a tag republished under the same name is not; the digest recorded with the measurements is how
  to check.
- Two configurations that could not produce a flagged name that opens in a plain LIST (a second
  namespace colliding with a real mailbox, and one prefixed `INBOX/`) are recorded in the
  measurements and the [email-imap runbook](../runbooks/email-imap.md), which says to rebuild them
  by hand after a bump; keeping them runnable was declined
  ([R-401](../refinements/tasks/401-the-rejected-probe-configurations-are-prose.md)).
- Dovecot's `vfile` ACL file lives inside the mailbox directory whose absence makes a name
  `\Noselect`, so this server cannot hold a name both flagged and shut.

## Alternatives rejected

- **`--volumes` on the `down` recipe**: it removes the volume only after a clean shutdown, removes
  any named volume the stack ever grows, and rests the promise on a recipe rather than the stack.
- **Binding the conf straight onto `/etc/dovecot/dovecot.conf`**, which stays passing when the
  configuration root is changed (decision 8).
- **A second Dovecot service** running the default `imap_fetch_failure`, for a row that would fix
  words no classification reads.
- **Putting the mail root in the constant registry**: a value with one place is not a coupling.

## Related

- [ADR-0056](ADR-0056-email-reader-answers.md) (the rules measured here),
  [ADR-0067](ADR-0067-image-volume-record.md) (the image-volume check),
  [ADR-0042](ADR-0042-cross-tree-constant-registry.md) (the registry that ties the fixture's names
  together).
- Readings: [imap-server-answers](../readings/imap-server-answers.md).
- Runbook: [email-imap](../runbooks/email-imap.md); module:
  [brain-email](../modules/brain-email.md).
