# The unfenced correction is unmeasured on the cortex, and the own texts are unrun against a Bridge

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Opened 2026-09-02 by the close of [530](530-a-sidecars-own-text-is-re-stamped-trusted.md), which
built the own-text overlay and left two measurements undone for want of a sitting. The ADR-0013
own-text addendum named the second cost of the old behaviour: a refused search reached the model
fenced, inside the region the preamble says never to obey, and both refusals are instructions
(rewrite the query from the field description, call `list_folders` before naming a folder).
Since the build those two sentences reach the model unfenced, and whether the shipped cortex now
follows them is a claim nobody has measured: the fenced case was never measured either, so there
is no before to compare against, and a correction the model reads and ignores costs a dispatch
per retry exactly as it did.

The second half is the live path. The build's end-to-end check drives the real `cortex_email`
server through `FastMCP.call_tool` into the real `McpToolRegistry`, so the sidecar's own
`SearchRefusedError` is recognized in-process. It has not been driven against the Bridge, where
the refusal originates as an IMAP `BAD` and the folder refusal as a `NO`, and where the
composition root's wiring, the reconnecting registry and the bound all sit between the sidecar and
the overlay.

**What would close it.** Two runs, both the agent's to make via Docker rather than the
maintainer's (AGENTS.md gate 3). First, with the GPU stack and the email sidecar up
([email-imap.md](../../runbooks/email-imap.md); the Bridge answers on loopback and every live run
sets `CORTEX_EMAIL_IMAP_TLS_INSECURE=true`), a `Converse` turn asking for mail with a query the
model is likely to write in a client's syntax, read for whether the second call is a rewritten
raw-IMAP query and whether a `send_email` that follows reaches the confirmation card; twenty
draws, not three, per the model-validation rule. Second, the same turn's audit line, read for
`trust=trusted` beside `ok=False` on the refused call, which is the whole live claim of the
overlay. If the cortex ignores the unfenced correction as often as it would a fenced one, the
overlay still buys the untainted send and the finding goes at the origin ADR as a measured cost
of the dialect rather than of the framing.

## Trail

- 2026-09-02: opened by the close of [530](530-a-sidecars-own-text-is-re-stamped-trusted.md).
