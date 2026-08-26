# Nothing prices what the reply envelope costs the answer rather than the tokens

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-26 by the close of
[R-456](456-a-constrained-request-loses-the-thinking-lever.md), whose live proof was the first
sight of the constrained shape answering without a reasoning trace.

Everything measured about the envelope so far is a length: decoded tokens, wall clock, characters
returned. Nobody has read whether the answer is as good. The first readings taken with the trace
off are not reassuring. Over the three report bodies the envelope measurement is built around, at
the shipped cap, every constrained run finished well inside it (63 to 89 decoded tokens, 223 to 395
characters) and **every one of the three narrated the task instead of performing it**: "The user
wants a comprehensive summary of the provided site report", "I need to summarize the provided text
while ensuring every single detail is retained", and one that spends its whole reply arguing the
instruction contradicts itself. The same bodies raw returned 1512 to 2211 characters of actual
summary. Read plainly, this model writes into `reply` what it used to write into
`reasoning_content` now that nothing else will take it.

**Why it was left.** Three draws from a 4B model price nothing, and the entry it comes from was a
defect with a live before and after, not a quality study. Acting here would mean changing the
grammar every delegated reply is decoded into on the strength of three readings, which is the shape
of mistake this backlog exists to refuse.

**What would close it.** The harness already runs both shapes over the same bodies, so the
measurement is a reading rather than a build: run the paired arms at the shipped cap with the tier
fixed and compare the replies as answers, not as sizes, over enough bodies that one thin draw is
visible as one. The honest outcomes are three: the envelope costs nothing and the reading above was
a draw, it costs a little and the niche it defends is still worth it (ADR-0028's argument is
format-laundering on a weak model, not answer quality), or it costs enough that the tool-less shape
wants a different grammar. Worth measuring in the same run: whether the model writes a better answer
when the envelope's `reply` property carries a description, since an empty schema tells it nothing
about what the field is for.
