# The cortex template ends the turn after a call message's text

**Status:** declined 2026-10-31
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

`to_openai_message` (`request.py` in `cortex_inference`) sends a round's call message with the
text the model wrote before its calls as `content`. llama-server's `/apply-template` on the
cortex (gemma-4-12B, build `b11977`) renders that message as the call, its result, then the text
and `<turn|>`, which ends the model's turn; the next round is then decoded after a finished turn,
and with no text the turn stays open after the result. In the draws of
[reply-repeat-across-a-tool-call.md](../../readings/reply-repeat-across-a-tool-call.md), 4 of the 5
W04 rounds that followed text written before a call began by writing that text again. The loop
now drops such a repeated opening sentence (`round_opening.py`), which hides the symptom, but the
next round still reads a prompt the template was not written for.

## What to do

1. Render the prompt of a call message with text and one without, as the readings did, and
   compare the decoded next rounds with the text sent in `content` and with it left out, or with
   an override template (`--chat-template-file`) that keeps the turn open. Write rows and a rule
   in a readings record before any draw; the counts above are the baseline's size.

## History

- 2026-10-30: filed from the repeated-sentence draws, where `/apply-template` showed the cause.
- 2026-10-31: declined, since `/apply-template` shows the template as written here but no form of
  the call message stops the next round repeating the text, so it is not the cause. On fixed second
  rounds, what ships opens with the sentence on 32 of 60 draws; with the text left out of `content`
  on 60 of 60, because the model answers again, and all 15 draws lose the number the first round
  wrote; with `<turn|>` removed as an override template would on 48 of 60; with the text sent as its
  own message before the call, which keeps the turn open on the stock template, on 38 of 60. No form
  met the rule written before the draws, so the call message and `OpeningHold` stay as they are
  ([readings](../../readings/reply-repeat-across-a-tool-call.md#the-form-of-the-call-message-result-2026-10-31)).
