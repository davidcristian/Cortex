# The replies around a refused send misstate what to do next

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-10-10

Two replies on the Linux shell ([readings](../../readings/overlay-email-flows.md#replying)):

- "Reply to Carla's invoice email saying ..." searched the mailbox first, so the send was refused
  with `DENIED_MSG`, and the reply told the person to ask again in a new message. Asked again in
  the same words, the model would search again and be refused again. ADR-0022 says "read that
  email, then reply" works in the next turn; it does only when the person writes the address,
  subject and body out, so the model reads no mail.
- After Deny, which returns `USER_DECLINED_MSG`, the reply said the assistant was ready to send
  and asked whether to go ahead, rather than saying the person had declined.

## What to do

Decide whether `DENIED_MSG` should tell the model what the person must write for the next turn to
be untainted (the recipient, subject and body in their own words), and whether the declined text
needs a sentence the model repeats. Each is a change to a text the model reads, so measure it on
the cortex with rows written before the run, and correct ADR-0022's next-turn sentence either way.

## History

- 2026-10-10: filed from the email flows on the Linux shell.
