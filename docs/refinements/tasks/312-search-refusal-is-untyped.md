# A refused search reaches the model as the IMAP library's own error

**Status:** landed 2026-08-19
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-18 by the close of [211](211-search-emails-query-dialect.md), which described the
`search_emails` dialect from a live pass so a model stops guessing at it. Describing the dialect
removes most wrong queries; it does not change what a wrong one returns. `ImapMailbox.search`
hands the query to imap-tools and lets whatever imaplib raises escape, so the model reads
`Error executing tool search_emails: UID command error: BAD [b'[Error offset=38]: expected
space']`, an offset into a wire command it never saw, from a library it is not told about.

That is the one thing AGENTS gate 5 names outright: explicit typed exceptions, at the adapter
boundary where the library's own type would otherwise leak. Every other refusal in this sidecar is
already shaped, the send path most of all.

**What would close it.** A typed error out of the `Mailbox` port, raised by `ImapMailbox` when the
server answers `BAD`, carrying the query it refused and pointing at the dialect the field
description already spells out, so the model's next attempt is a correction rather than a second
guess. The fake in the contract test raises the same type on the same trigger, which is what makes
it a port change rather than an adapter detail. Worth checking in the same sitting whether the
brain's tool registry flattens the message on the way out
(`brain/packages/tools/src/cortex_tools/registry.py`), since a shaped error the registry restates
as `Error executing tool ...` buys only half of what it costs.

## Trail

- 2026-08-18: opened by the close of [211](211-search-emails-query-dialect.md), whose live pass
  reproduced the refusal verbatim while deliberately not widening its own slice to reshape it.
- 2026-08-19: Landed as a failure channel on the port rather than one wrapped call. `cortex_email`
  declares `MailboxError` and its narrower `SearchRefusedError` (`errors.py`, the sidecar being
  unable to import the core), and the line between them is whether rewriting the query changes
  anything: every other failure heals when the machine is fixed, this one only when the model
  writes a different search, so it carries the `query` and points at the field description instead
  of restating the dialect. `ImapMailbox` classifies by looking rather than assuming, since
  imaplib's `IMAP4.abort` is a subclass of the error a `BAD` raises and a dropped connection
  reported as a refusal is a rewrite loop that cannot end; everything else it raises, imap-tools'
  own `NO` exceptions included, crosses as `MailboxError` with the cause chained. The registry
  question this entry raised is answered: `McpToolRegistry` restates nothing, and the
  `Error executing tool ...` prefix comes from FastMCP inside the sidecar, so `search_emails`
  answers a refusal with its own `isError` `CallToolResult` and the prefix is gone from the
  refusal while staying on a mailbox that really could not answer. The port gained the shared
  contract it never had (`mailbox_contract.py`, four checks over the fake and the adapter, one of
  them that the message carries no fragment of the wire answer), and the fake and the imap-tools
  stand-in moved into shared test modules. Verified live: a real Bridge answered
  `from:someone@example.com` with the same `BAD` this entry quotes and it came back typed. Opened
  [318](318-a-folder-refusal-is-untyped.md), the sibling guess the same tools describe, and
  [319](319-a-refusal-taints-the-turn.md), a search that read nothing closing the outbound surface
  behind it.
