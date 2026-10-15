# A recap fold over a message past the context fails on every later turn

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-10-15

On the Linux shell on 2026-10-15 a person pasted a 60,175-character log (36,546 gemma-4 tokens)
into a new chat ([readings](../../readings/overlay-long-and-unusual-input.md#a-pasted-log-past-the-context)).
That turn ended with `CONTEXT_OVERFLOW_NOTE`. The next turn's window dropped the log, as it is over
the 24,000-character budget, and `SummarizingHistoryWindow` tried to fold it into a recap. The fold
prompt holds every newly dropped message whole, so the cortex refused it at 37,138 tokens, the
brain logged `history recap unavailable; falling back to the plain window` with the traceback, and
the turn answered from the plain window. The third turn did the same twice, at 37,138 and 37,140
tokens. No recap is stored, so every later turn of the chat pays a refused fold and the folding
status the person sees.

The recall judge also sent the whole 60,175-character message as its query and was refused at
43,563 tokens, then fell back to the unjudged ranking, as ADR-0038 allows.

## What to do

Bound what one fold reads: `build_recap_messages` can cut each dropped message to a fixed number of
characters, sized on the 1.65 characters a token measured on the log, with a marker saying it was
cut, so a fold always fits the context. Alternatively store a recap that only names the message as
too long to summarize, so the boundary moves on. Pick one in ADR-0038, test it with the fake
backend, and check on the shell that the third turn logs no refused fold.

## History

- 2026-10-15: filed from the long-input flows on the Linux shell.
