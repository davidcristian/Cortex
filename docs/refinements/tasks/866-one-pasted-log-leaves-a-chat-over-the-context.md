# One pasted log leaves a chat over the context for several turns

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)
**Verified:** 2026-10-15

On the Linux shell on 2026-10-15 a person pasted a 22,206-character server log into a new chat and
asked about its last line ([readings](../../readings/overlay-long-and-unusual-input.md#a-pasted-log-near-the-context)).
The cortex refused the prompt at 16,965 tokens against its 16,384, and the turn ended with
`CONTEXT_OVERFLOW_NOTE`, as decision 7 says. The next two questions in the same chat, "What colour
is a ripe lemon? One word." and "Name one planet. One word.", ended with the same note and no
answer. The note tells the person to send a shorter message, which does not help.

The cause is the window's unit. The log is 1.65 characters a gemma-4 token, against the 3.6 to 4.7
that decision 3 sized the 24,000-character budget on, so the whole log fits the budget and stays in
every later window while its tokens alone fill most of the context. Each failed turn adds about 250
characters of question and note, so the log leaves the window only after about six more turns. Two
pastes of half that size in one chat reach the same state. Hex identifiers, timestamps and
punctuation are the dense text a person pastes most often.

## What to do

The refusal already says by how much the prompt is over: the 400 body has `n_prompt_tokens` and
`n_ctx`. On a `ContextOverflowError` before any text, the turn can drop its oldest windowed turns
until the estimated excess is gone and ask once more, and end with the note only when the newest
turn alone does not fit. Write that as a decision in ADR-0014, with a fake backend test for the
retry, the single retry and the newest-turn case, and measure it on the same log through the shell.
A note that names the message as too long, when the newest turn alone is over, is part of it.

## History

- 2026-10-15: filed from the long-input flows on the Linux shell.
