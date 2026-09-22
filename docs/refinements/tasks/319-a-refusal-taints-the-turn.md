# A tool result with no external content still taints the turn

**Status:** done 2026-09-02
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

The email sidecar writes its own refusal, so the sentence a model reads when its search is refused
is text from this repo, and the turn treats it as mail.

The path is short and no step is wrong on its own. `McpToolRegistry.invoke` builds every
`ToolResult` at the `Trust.UNTRUSTED` default, since a sidecar's claim about its own content can be
influenced by an attacker and the trust decision belongs to the brain. `dispatch_round` then
observes every dispatched result outside every branch, so no dispatch goes unrecorded.
`TaintLedger.mark` acts on the trust value alone. So a search the server refused, which read no
message and returned nothing but our own correction, closes the outbound surface for the rest of
the turn: a later `send_email` is denied with `DENIED_MSG`, and the user is told to ask again in a
fresh message.

The cost is small and real: a model that mistypes a query and then wants to send loses the send to
a mailbox it never read. There was no channel on which a sidecar could say "this result is my own
refusal, not content I fetched", and inventing one a hostile sidecar could set is worse than the
false positive. What this entry asked for is a recorded decision about whether a result that is
untrusted by default may ever be exempt from taint, and on what evidence. Declining was a valid
outcome.

## History

- 2026-08-19: Opened by the close of [312](312-search-refusal-is-untyped.md), which gave the email
  sidecar a refusal in its own words and found that reading it costs the turn its outbound surface
  exactly as reading a message would.
- 2026-09-02: Decided and recorded as ADR-0013 decision 10. A result that is untrusted by default
  is marked trusted only by the brain, in a composition-root overlay, and only when its whole
  content is byte-equal to text this repo holds in code, rendered with the argument the brain put
  on the call; nothing from the wire takes part, `isError` and `_meta` included. The deciding fact
  is that a sidecar can already leave a turn untainted by failing, so the only capability an
  exemption must withhold is attacker bytes reaching the model untainted, which byte equality
  withholds. Two claims here were corrected against the code: the refusal includes the model's own
  argument as well as this repo's text, and it reaches the model fenced, so the correction it
  states sits inside a region the preamble says never to obey. The build is
  [530](530-a-sidecars-own-text-is-re-stamped-trusted.md); the pattern it follows turned out to be
  unchecked for the source key, filed as
  [531](531-the-source-declaration-key-is-written-in-two-trees-and-no-check.md); and the same rule closed
  [079](079-per-remote-tool-trust-overrides.md).
