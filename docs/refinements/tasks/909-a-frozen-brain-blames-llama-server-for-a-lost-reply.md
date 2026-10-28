# A frozen brain blames llama-server for a lost reply

**Status:** open, waiting for its trigger
**Area:** inference
**Origin:** [ADR-0007](../../adr/ADR-0007-model-manager-inference.md)
**Trigger:** a turn in flight across a real sleep of the host ends in `no reply within` on the overlay, or the brain logs the stall line for a reply the model host finished
**Verified:** 2026-10-28

When the brain process is frozen past `CORTEX_INFERENCE_STALL_TIMEOUT_S` (120 s) in the middle
of a reply, the read deadline runs out while it is frozen. At the thaw the brain logs
`inference failed mid-turn` with `llama-server sent nothing for model 'cortex' for 120 s, the
longest a stream may stay silent`, although only the brain was frozen. The body had already ended
the turn on its own 120 s bound with `no reply within 120s`. The chat keeps the question with no
reply.

Reproduction ([readings](../../readings/overlay-idle-and-expiry-flows.md#the-brain-frozen-across-a-reply-and-a-reminders-due-time)):
send a request on the Linux shell, `docker pause` the brain 4 s later, `docker unpause` it 150 s
later. A freeze is counted by the monotonic clocks of the brain and the body; whether a real sleep
of the Windows host or of the WSL VM is counted was not measured, which is what the trigger asks.

## What to do

When the trigger fires, decide from that run whether the stall line should name a late event loop
(measured as the gap between the deadline and the moment the loop noticed it) instead of
llama-server, and whether the body's bubble should say the brain stopped answering rather than
show the raw bound.

## History

- 2026-10-26: filed from the idle and expiry flows on the `cortexn8` stack.
- 2026-10-28: checked again and not fired, and corrected: the stall error now names its bound, so
  the body quotes the line the brain logs today, which still blames llama-server.
