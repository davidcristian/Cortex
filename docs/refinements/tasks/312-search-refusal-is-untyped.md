# A refused search reaches the model as the IMAP library's own error

**Status:** done 2026-08-19
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

Describing the `search_emails` dialect removes most wrong queries; it does not change what a wrong
one returns. `ImapMailbox.search` handed the query to imap-tools and let whatever imaplib raised
escape, so the model read `Error executing tool search_emails: UID command error: BAD [b'[Error
offset=38]: expected space']`, an offset into a wire command it never saw, from a library it is not
told about.

AGENTS requires explicit typed exceptions at the adapter boundary, where the library's own type
would otherwise escape. Every other refusal in this sidecar is already typed.

The fix is a typed error on the `Mailbox` port, raised by `ImapMailbox` when the server answers
`BAD`, containing the query it refused and pointing at the dialect the field description already
describes, so the model's next attempt is a correction rather than a second guess. The fake in the
contract test raises the same type on the same input, which makes it a port change rather than an
adapter detail. Worth checking at the same time whether the brain's tool registry flattens the
message on the way out (`brain/packages/tools/src/cortex_tools/registry.py`).

## History

- 2026-08-18: Opened by the close of [211](211-search-emails-query-dialect.md), whose live run
  reproduced the refusal word for word while deliberately not widening its own slice to fix it.
- 2026-08-19: Fixed as a failure channel on the port rather than one wrapped call. `cortex_email`
  declares `MailboxError` and its narrower `SearchRefusedError` (`errors.py`, the sidecar being
  unable to import the core), and the difference is whether rewriting the query changes anything:
  every other failure goes away when the machine is fixed, this one only when the model writes a
  different search, so it includes the `query` and points at the field description. `ImapMailbox`
  classifies by inspecting the error rather than assuming, since imaplib's `IMAP4.abort` is a
  subclass of the error a `BAD` raises and a dropped connection reported as a refusal would be a
  rewrite loop that cannot end; everything else, imap-tools' own `NO` exceptions included, crosses
  as `MailboxError` with the cause chained. The registry question is answered: `McpToolRegistry`
  restates nothing, and the `Error executing tool ...` prefix comes from FastMCP inside the
  sidecar, so `search_emails` returns a refusal as its own `isError` `CallToolResult` and the
  prefix is gone from the refusal while staying on a mailbox that really could not answer. The port
  gained the shared contract test it never had (`mailbox_contract.py`, four checks over the fake
  and the adapter, one of them that the message contains no fragment of the wire answer), and the
  fake and the imap-tools stand-in moved into shared test modules. Verified live: a real Bridge
  answered `from:someone@example.com` with the same `BAD` this entry quotes and it came back typed.
  Opened [318](318-a-folder-refusal-is-untyped.md), the sibling guess the same tools describe, and
  [319](319-a-refusal-taints-the-turn.md), a search that read nothing closing the outbound surface
  behind it.
