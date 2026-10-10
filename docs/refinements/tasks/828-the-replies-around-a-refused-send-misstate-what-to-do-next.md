# The replies around a refused send misstate what to do next

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-10-10

After Deny on the confirmation card the dispatcher returns `USER_DECLINED_MSG`, and four of five
replies said the email was not sent because it "requires your explicit approval" and offered to
send it ([readings](../../readings/overlay-email-flows.md#a-refused-send)). The text must stay true
for three endings, a pressed Deny, a card that timed out and a turn with no confirmer, because
`Confirmer.confirm` returns a bool. A text true for all three passed 3 of 5; the text naming Deny
(row D1b) passed 5 of 5 but is false for the other two.

## What to do

Type the confirmer's answer: `Confirmer.confirm` returns approved, declined (a pressed Deny) or
unanswered (a timeout, a closed stream, no confirmer), and the dispatcher returns the D1b text for
declined and the current text for unanswered. It changes the port, `RpcConfirmer`,
`RecordingConfirmer`, the confirmer contract test, ADR-0013 decision 4 and ADR-0022 decision 2.
Rerun D1 after the change.

## History

- 2026-10-10: filed from the email flows on the Linux shell.
