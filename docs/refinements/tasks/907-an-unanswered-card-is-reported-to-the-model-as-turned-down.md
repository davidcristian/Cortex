# An unanswered card is reported to the model as turned down

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

A confirmation card that times out after `CORTEX_SEAM_CONFIRM_TIMEOUT_S` closes on the overlay with
nothing drawn in its place, because ADR-0022 expects the model's reply to explain the denial. The
model is given `UNANSWERED_MSG`, which starts with `DECLINED:` and says the user did not approve.
In six unanswered `escalate_to_brain` cards no reply said the card had gone unanswered or expired:
two said the request "was declined", three that it "requires your explicit approval", and the
first, at the 120 s default, wrote the proof itself and did not mention the deep model at all. A
person who stepped away reads that they declined something they never saw answered.

Reproduction ([readings](../../readings/overlay-idle-and-expiry-flows.md#a-confirmation-card-left-unanswered-past-its-timeout)):
recreate the brain with `CORTEX_SEAM_CONFIRM_TIMEOUT_S=8` and send "Please hand this to the deep
model: give a careful proof that the square root of 2 is irrational." over `Converse` five times,
never answering the card.

## What to do

1. Write the rule into the readings before any row: ten rows of the request above, the card never
   answered; a row passes when its reply says the request was not answered in time or expired and
   does not say the person declined it. Draw the baseline on the tree first.
2. The candidate is a result text of its own for a timeout (the card waited, nobody answered,
   nothing was done, ask again to retry), distinct from a pressed Deny and from a closed stream.
   It ships if it passes 8 or more of 10 where the baseline passes 2 or fewer. Also decide whether
   the overlay should leave a line where the card was.

## History

- 2026-10-26: filed from the idle and expiry flows on the `cortexn8` stack.
