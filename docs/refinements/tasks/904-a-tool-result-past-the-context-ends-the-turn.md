# A tool result past the context ends the turn

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

A tool result goes into the next model call whole, whatever its length. A file read that returns
more than the context holds makes llama-server refuse the next request, and the engine ends the
turn with `CONTEXT_OVERFLOW_NO_TEXT_NOTE`, which tells the person to start a new conversation or
send a shorter message. Their message was short; the model never sees that the result was too
long, so it cannot read the file again with `head` or `tail`, which the filesystem tools offer.

Reproduction ([readings](../../readings/overlay-tool-failure-flows.md#a-file-far-past-the-context)):
put a 1.97 MB log in the sidecar's root and ask "Read the whole of server-log.txt and count how
many lines mention worker-4." on the brain directly. The cortex read the file
(`result_chars=1966260`), the next request was 1,130,411 tokens against a context of 16,384, and
the reply was the note above after 12.8 s. The chat was not damaged: the result is not stored, so
the next turn in the same chat starts with the two short messages only.

## What to do

1. Cut a tool result to a share of the context before it enters the prompt, and end the cut text
   with a line the model can act on (how much was left out, and that `head` or `tail` reads part
   of a file). Decide the share and write it into ADR-0009.
2. Test over fakes that a long result is cut and the turn goes on, and repeat the reproduction.

## History

- 2026-10-26: filed from the tool failure flows on the `cortexn8` stack.
