# The assistant reports a send that never ran

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-10

On the Linux shell a chat holding one approved send was asked for a second send, and the model made
no tool call at all and answered that the email had been sent. Nothing was audited, no card was
shown, and the SMTP sink stored nothing. It happened in two chats of two
([readings](../../readings/overlay-email-flows.md#replying)). Reproduction, with the email sidecar
and send enabled: in a fresh chat ask "Send an email to alice@example.com with subject A and body
B", approve the card, then ask "Send an email to bob@example.com with subject C and body D". The
second reply says it was sent; `docker logs` shows no `tool=send_email` line for it.

The persisted history holds only the user and assistant text (ADR-0021 decision 2), so what the
model reads of the first turn is a request followed by "I've sent that email", with no call
between them, and it repeats that shape. Any tool with a visible effect can be claimed the same
way; the person has no sign on screen that no call was made.

## What to do

Decide between replaying a short record of each earlier turn's tool calls and their outcome with
the history (a store record kind beside `message`, which every reader of the list must skip or
read), and a check on the reply. Measure the chosen change against this reproduction and against
a turn that should answer from history without a call, with rows written before the run.

## History

- 2026-10-10: filed from the email flows on the Linux shell.
