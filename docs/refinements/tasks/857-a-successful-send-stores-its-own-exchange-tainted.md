# A successful send stores its own exchange tainted

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md) decision 10
**Verified:** 2026-10-14

The email sidecar answers a send it handed to the server with one line, `confirmation` in
`cortex_email/drafts.py`: `email sent to <to> (subject: "<subject>")`. `McpToolRegistry` builds
that result at the `Trust.UNTRUSTED` default, and no `OwnText` entry in
`cortex_orchestrator/own_texts.py` names `send_email`, so the send taints its own turn after it
ran. Under `CORTEX_MEMORY_ON_TAINTED=record` the exchange is then stored tainted, and a later
request like it recalls that row and is blocked with `RECALL_DENIED_MSG` until the person has the
untrusted memories forgotten. On the stack every one of six approved sends stored one tainted row
([forget-untrusted-memories.md](../../readings/forget-untrusted-memories.md)).

## What to do

The line is rendered entirely from the call's own `to` and `subject` arguments when the server
refused no recipient, which is the case ADR-0013 decision 10 re-stamps trusted. Add an `OwnText`
for `send_email` that renders it from the arguments, restating the template beside the other
email texts with its `emailcouplings.py` entry, so a byte change on either side fails
`crosscheck`. A reply that names refused recipients holds addresses the server wrote and stays
untrusted. Then draw the readings' SF row again and check that the send stores a trusted row.

## History

- 2026-10-14: filed while closing
  [R-848](848-nothing-lets-the-person-out-of-a-recall-tainted-block.md), whose live rows showed
  every approved send storing a tainted row.
