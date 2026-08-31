# The answer the folder rule reads holds the name the caller sent

**Status:** open, fix when it bites
**Area:** email-confirmer
**Trigger:** a third IMAP server, or one whose refusal for a mailbox that is there and shut echoes the name it refused
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

`_select` in `brain/packages/email/src/cortex_email/imap.py` classifies a refused SELECT by
lower-casing `str(err)` and looking for a measured phrase or an RFC 5530 code in it. That string is
what imap-tools rendered out of the refused command, and a server that names the mailbox it refused
puts the caller's own folder name inside it: Dovecot answers `Mailbox doesn't exist: <name>`. So a
caller supplies part of the text the classification reads, and a folder named `[NOPERM] archive` or
`no such mailbox` is a name whose refusal carries the rule's own needles.

Today this is harmless on both servers the repo talks to, and it was measured rather than assumed.
The echo really happens, verbatim from the probe:

    EXAMINE "[NOPERM] archive"   NO Mailbox doesn't exist: [NOPERM] archive (0.001 + 0.000 secs).
    EXAMINE "no such mailbox"    NO Mailbox doesn't exist: no such mailbox (0.001 + 0.000 secs).
    EXAMINE "[CANNOT] thing"     NO Mailbox doesn't exist: [CANNOT] thing (0.001 + 0.000 secs).

The direction that could cause harm is the fail-safe one, a mailbox that is really there and shut
being reported missing, and reaching it needs a refusal that both declines a real mailbox and
echoes the name. Dovecot's is `[NOPERM] Permission denied` with no name in it, and the Bridge
cannot produce a shut mailbox at all. In the other direction the echo changes nothing: a name no
mailbox has is answered `Mailbox doesn't exist: <name>` whatever the name is, so the phrase that
matches is the server's own either way.

**What would close it.** Reading the response code and the text out of the refused command's data
rather than out of a rendered exception message, which is where the boundary between what the
server said and what the caller sent actually is. imap-tools carries the raw `(status, data)` on
`MailboxFolderSelectError`, so the parse is available without reaching past the library; what has to
be decided is how much of an IMAP response-code grammar to write for a needle that is currently one
`in` against a string. The cheaper half, and the one worth doing first if this ever bites, is to
stop matching anywhere in the message and match only the code at the front of the data line, which
is the one position RFC 5530 lets a code appear in.
