# Readings: IMAP server answers

What the two IMAP servers this repo reaches answer to the commands the email reader sends, verbatim.
Cited by [ADR-0056](../adr/ADR-0056-email-reader-answers.md) (the rules that read these answers) and
[ADR-0057](../adr/ADR-0057-imap-probe-server.md) (the fixture that produces the second server's).
The servers are Proton Mail Bridge (03.25.00 until 2026-08-18, 03.26.00 since) on loopback, read-only
throughout, and the probe, `dovecot/dovecot:2.3.21` build `47349e2482`.

Method, unless a section says otherwise: through `ImapMailbox`, or a raw imaplib dialogue past the
port, against the Bridge with `CORTEX_EMAIL_IMAP_TLS_INSECURE=true`, and against the probe after
`just up-imap-probe`. Every Dovecot answer ends in a timing suffix such as `(0.001 + 0.000 secs).`,
omitted below where it adds nothing.

## The probe image

**2026-09-12.** `dovecot/dovecot:2.3.21` resolves to
`sha256:1c18c756f20d03867077a1b509a6e2e3008ab1eafa56377b6f2eca12dc1ba581` in the registry
(`docker manifest inspect --verbose`) and in the host's cache (`docker image inspect`). Every
probe reading below was taken on that build.

## The search dialect

**2026-08-18**, Bridge 03.25.00, a folder of 1205 messages, `EXAMINE` and hit counts only, in the
form imap-tools sends (`UID SEARCH CHARSET US-ASCII ...`).

- **Accepted:** `ALL` (1205); `SUBJECT`, `FROM`, `TO`, `CC`, `BCC`, `BODY`, `TEXT` and
  `HEADER "Name" "value"` with quoted arguments; `SINCE` (417) and `BEFORE` (788, partitioning the
  1205 with `SINCE`), `ON`, `SENTSINCE`, `SENTBEFORE`, `SENTON`; the standalone flags `SEEN`,
  `UNSEEN`, `ANSWERED`, `UNANSWERED`, `FLAGGED`, `UNFLAGGED`, `DRAFT`, `UNDRAFT`, `DELETED`,
  `UNDELETED`; `LARGER` and `SMALLER` in bytes. Juxtaposition ANDs (`FROM "..." SINCE 01-Jan-2026`
  found 8, fewer than either alone), `OR` takes the two criteria after it, `NOT` the one after it,
  and parentheses group.
- **Refused:** `from:someone@example.com` and `subject:cortex` (`BAD ... expected space`); an ISO
  date (`expected - after year`); an unquoted multi-word argument (`unknown search key`);
  `KEYWORD` with the flag it was probed with.
- A folder name no mailbox has: `no such mailbox`. A `SINCE` search cut to 4 matches in the virtual
  All Mail folder returned its uids 1 to 4, the first four in uid order.

Method: the `integration`-marked criteria row in `test_email_live.py`, which re-runs one query per
family the description names.

## A refused SELECT

**2026-08-21 and 2026-08-22**, through `ImapMailbox` and a raw dialogue.

| SELECT of | Bridge | probe |
| --- | --- | --- |
| a name no mailbox has, any shape (bare, child of a real folder, quoted, non-ASCII) | `NO no such mailbox`, no response code | `NO Mailbox doesn't exist: <name>` |
| `""` | `NO no such mailbox` | `NO [CANNOT] Invalid mailbox name: Name is empty` |
| `Parent/`, `/Parent`, `Parent//Child` | not asked | `NO [CANNOT] Invalid mailbox name:` then `Ends with hierarchy separator`, `Begins with hierarchy separator`, `Has adjacent hierarchy separators` |
| `INBOX/../etc`, `~root` | not asked | `NO [CANNOT] Invalid mailbox name:` then `Contains '..' part`, `Begins with '~'` |
| `Bad\Name`, two spaces | not asked | `NO Mailbox doesn't exist: <name>` |
| `Guarded`, listed and shut by an ACL | (the Bridge has no shut mailbox) | `NO [NOPERM] Permission denied` |
| `Parent`, a `\Noselect` node | (its flagged parents open) | `NO Mailbox doesn't exist: Parent` |

**2026-09-08 and 2026-09-17**, the probe. A name sent to EXAMINE is echoed after the phrase:
`EXAMINE "[NOPERM] archive"` answers `NO Mailbox doesn't exist: [NOPERM] archive`, and
`"no such mailbox"` and `"[CANNOT] thing"` likewise. A real mailbox named `no such mailbox`, shut by
the same ACL, answers `NO [NOPERM] Permission denied` with no name, as `Guarded` does. In imap-tools
1.13.0, `MailboxFolderSelectError` keeps the refused command's `(status, data)` as `command_result`.

## Listings

**2026-09-09**, the Bridge: 19 names listed, 19 open, 19 offered by `list_folders`. Two have a flag
the reader asks about, `Folders` and `Labels`, `('\Noselect', '\Unmarked')`, and both open. The
rest: `INBOX` (`\Noinferiors`), `All Mail` (`\All`), `Archive`, `Drafts`, `Sent`, `Spam` (`\Junk`),
`Starred` (`\Flagged`), `Trash`, and nine `Folders/...` children. The Bridge advertises
`AUTH=PLAIN ID IDLE IMAP4REV1 STARTTLS` and answers an extended LIST with
`BAD [Error offset=17]: expected CR`.

**2026-09-12**, the probe's plain `LIST "" "*"`, past the port, each name then opened:

```
Feigned            (\HasChildren \UnMarked)     opens
Feigned/Followed   (\HasNoChildren \UnMarked)   opens
Guarded            (\HasNoChildren)             NO [NOPERM] Permission denied
INBOX              (\HasNoChildren)             opens
Parent             (\Noselect \HasChildren)     NO Mailbox doesn't exist: Parent
Parent/Child       (\HasNoChildren \UnMarked)   opens
Sealed             (\HasNoChildren)             opens
```

`list_folders` offers six, dropping `Parent`. `\UnMarked` appears once something has searched the
mailbox, so a fresh container lists `Feigned` as `(\HasChildren)` alone.

**2026-08-22 and 2026-08-23**, the probe's other listings:

```
LIST "" "*" RETURN (CHILDREN)       (\Noselect \HasChildren) "/" Parent
LIST "" ("*") RETURN (SPECIAL-USE)  (\Noselect) "/" Parent
LIST (SUBSCRIBED) "" "*"            (\Subscribed \NonExistent) "/" Ghost
LIST "" "*"                         Ghost is not returned at all
LSUB "" "*"                         () "/" Ghost
EXAMINE Ghost                       NO Mailbox doesn't exist: Ghost
LSUB "" "%"                         (\Noselect) "/" Feigned
EXAMINE Feigned                     OK
```

`Parent` is `\Noselect` under every extended LIST the server accepts, never `\NonExistent`.

**2026-09-08**, the probe's ACL backend (`acl = vfile`) reads `dovecot-acl` from
`<mailbox>/dbox-Mails/`, and that directory's absence is what makes a name `\Noselect`. Creating it
under `Parent` and writing `owner l` turned `Parent (\Noselect \HasChildren)`, refused as missing,
into `Parent (\HasChildren)`, refused `[NOPERM]`. The global form `acl = vfile:<path>` is untried.

**2026-08-23**, two configurations tried for a flagged name that opens in a plain LIST, both
failing: a second namespace `prefix = Shared/` beside a real mailbox `Shared` listed the name twice,
`(\HasNoChildren)` and `(\Noselect \HasChildren)`, and a SELECT answered
`NO Mailbox doesn't exist: Shared`; a namespace `prefix = INBOX/` merged with the real `INBOX` as
`(\HasChildren)`, unflagged, and opened.

## Reads by uid, and a search in a folder holding no mail

**2026-09-05 and 2026-09-15**, Bridge 03.26.00 in every folder of the account (5 of 19 hold no
mail), and the probe.

| asked | Bridge | probe |
| --- | --- | --- |
| `EXAMINE` of a folder holding no mail | `OK [b'0']` | `OK [b'0']` |
| `UID SEARCH CHARSET US-ASCII UID 999` there | `NO no such message` (also for `1`, `4294967290`) | `OK`, nothing found |
| the same in a folder holding mail | `OK`, nothing found | `OK`, nothing found |
| `UID SEARCH ... ALL` or `SUBJECT "cortex"` in a folder holding no mail | `OK`, nothing found | `OK`, nothing found |
| `from:someone@example.com` there | `BAD [Error offset=38]` | not asked |
| `UID FETCH 999 (BODY.PEEK[] UID FLAGS RFC822.SIZE)`, any folder | `OK`, no data | `OK`, no data |
| a message another session expunged | not asked | `OK`, no data |

**2026-09-05**, a `UID FETCH` of a string that is not a uid:

| `UID FETCH` of | Bridge | probe |
| --- | --- | --- |
| `abc`, ` 1`, `1 2` | `BAD [Error offset=16]: expected valid digit for number` and siblings | `BAD Invalid uidset` |
| `0` | `BAD [Error offset=17]: expected non zero number` | `BAD Invalid uidset` |
| `01` | message 1 | nothing to answer with |
| `2,1`, `1:*` | every message in the set | `OK`, no data |
| `4294967296` | `OK`, no data | `BAD Invalid uidset` |

## A read the server declines

**2026-09-05**, the probe, a message appended and then made unreadable to the mail process
(`chown root`, `chmod 000`), one `imap_fetch_failure` setting at a time:

| setting | the FETCH answered |
| --- | --- |
| `disconnect-immediately`, the default | `* BYE FETCH failed: Internal error occurred. Refer to server log for more information.` and the connection dropped |
| `disconnect-after` | the same BYE |
| `no-after` | `NO [SERVERBUG] Internal error occurred. Refer to server log for more information. [<timestamp>]`, and a `NOOP` after it answered `OK` |

The message's file removed rather than shut answered `* BYE IMAP session state is inconsistent,
please relogin.`; an ACL of `owner l` written while a session had the mailbox open left that
session's FETCH `OK` and gave a fresh one `NO [NOPERM]` at SELECT, since the read right is checked
when the mailbox opens.

**2026-09-15**, the default setting again: imaplib raised `IMAP4.abort('command: UID => FETCH
failed: Internal error occurred. ...')`, the same words, and imap-tools' `logout` after the drop
raised nothing, so the port wraps the FETCH's own words on the read and search paths alike.

**2026-09-15**, `search(Sealed, ALL, limit)` with two readable messages saved beside the sealed one:
with the sealed message at uid 1, refused `NO [SERVERBUG]` with nothing yielded; with it at uid 3,
`limit=1` and `limit=2` answered normally and `limit=3` and `limit=5` were refused after uids 1 and
2 had been fetched, since imap-tools cuts the uid list to the limit and sends one FETCH per uid.

## What the cortex does with a uid

**2026-09-06**, the cortex tier started from the model host's own argv, over the real `cortex_email`
server and a mailbox of four messages in one folder and none in another; twenty seeded draws a
variant (`tests/test_uid_reading_live.py`).

| row | variant | counts |
| --- | --- | --- |
| copied | described (shipped) | listed 20/20 |
| copied | `uid` description stripped | listed 20/20 |
| `carried` | described (shipped) | clean 20/20 (none into the empty folder) |
| `carried` | stripped | clean 20/20 |
| after a not-found answer | corrected (shipped) | retried with a listed uid 20/20, searched 0/20 |
| after a not-found answer | the answer without its correction | retried 20/20 |
| after a not-found answer | bare `MCP tool 'read_email' failed` | retried 20/20 |

Every draw of every variant produced the same call at every seed, and the request quotes a listing
line almost word for word, so this is one result per variant rather than a distribution.
