# Readings: a repeated block, a stopped tool server and the forget card, on the Linux shell

What the overlay showed for three brain behaviours seen until then only over `Converse` from the
host: the repeated block check of [reply loop](reply-loop.md), the named server text of a tool
server that stops answering ([tool call cut off](tool-call-cut-off.md)), and the
`forget_untrusted_memories` card of [forget-untrusted-memories.md](forget-untrusted-memories.md).
The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## The rig

**2026-10-14**, the debug shell of the tree loading the overlay from Vite, on `Xvfb` and driven
with `xdotool`, frames grabbed with `ffmpeg` once a second or faster. The stack is the shared test
stack of that night: gemma 12B as the cortex on the GPU at the server's default sampling, the file
and email sidecars, `CORTEX_MEMORY_ON_TAINTED=record`, the default `global` scope, `judge` recall
and `CORTEX_TOOLS_ON_UNAVAILABLE=skip`. Stored replies were read from the session list in Redis,
tool calls from the brain's audit lines and memory rows from `psql`. SM clock after the flows: 0.60
of `clocks.max.sm`.

## A requested repeat

- **A line the message names.** "Write the line "Remember to bring your sheet music to practice."
  five times, one per line, and nothing else." ran to its end: five lines, no note.

### A requested repeat of a line the model writes

"Make up one short sentence of advice for a choir singer, then write that exact sentence ten
times, one per line, and nothing else." While it streamed, the chip showed fragments of the
model's reasoning; the reply then showed three copies of "Always focus on your blend with the
group." and `REPEATED_LINE_NOTE` in the same frame, since the brain sends the note right after the
third copy. The person asked for ten copies, so this is a request the check cuts as a loop: filed
as [R-858](../refinements/tasks/858-a-requested-repeat-of-a-line-the-model-writes-ends-at-its-third-copy.md).

- **The stored reply** held the three copies, `"\n\n\n"` and the note, so the overlay drew two
  blank lines above the note, while it streamed and again when the chat was opened from the list.
  Reasoning is not stored, so the resumed chat has no "Thoughts" row.
- **Asking again** in the same chat ("Please write all ten lines.") gave the same three copies and
  the note again.
- **After the fix** (the note adds only the line breaks one blank line needs), the same request
  with "about ten words" stored three copies, `"\n\n"` and the note, drawn with
  one blank line. A run whose made up sentence was "Support your tone.", 18 characters, wrote all
  ten copies with no note, since a line under 20 characters is not counted.

## A tool server that stops during a read

The [cut off read rig](store-and-sidecar-outages.md#the-filesystem-sidecar): "Read choir-rota.txt
in my files and tell me who sings in week 2.", the file sidecar paused once the brain audits a
listing call and killed after a delay, then started again.

- **Killed 8 s after the pause.** The cortex took longer than 8 s to write its read call, so the
  call found the server already gone and returned `SERVER_DOWN_MSG` ("the filesystem tool server
  is not answering, so 'read_text_file' did not run"). `read_file` and `list_directory` failed the
  same way, a subagent was spawned and could not read it either, and the reply read "The
  filesystem tool appears to be unresponsive at the moment. Please try again in a few minutes".
- **Killed 20 s after the pause.** The `read_text_file` row and "waiting for a tool to finish" stayed
  under the question for the whole pause, and the call ended at the kill, again with
  `SERVER_DOWN_MSG`: `AggregateToolRegistry.invoke` lists every server before it routes a call,
  so the frozen server held the listing, not the call, and the call never reached it. `CUT_OFF_MSG`
  needs the server to stop after that listing answers, which a pause from the host cannot time.
  The reply read "I'm unable to read the file `choir-rota.txt` because the filesystem tool server
  is currently not responding", offered to read a pasted copy, and named no content.
- Neither reply blamed the file or quoted an adapter error, as the reply in the same rig did before
  the server was named. The chip shows each call's tool row and the status line; a call's failure
  changes neither, and the status line does not name the server while the call waits.

## Forgetting from the overlay

All in one chat, after memory was emptied and the two seed chats of
[recall-tainted-send.md](recall-tainted-send.md) stored one tainted row each. "<own>" is the
Bridge account's own address.

1. **The send**, row S's request: recall returned one hit marked tainted, `send_email` returned
   `RECALL_DENIED_MSG` with no card, and the reply read "If you would like to proceed, you can ask
   me to forget the memories derived from untrusted content, and then you can ask me to send the
   email again." Memory: 3 rows, all tainted.
2. **Deny.** "Please forget the memories derived from untrusted content." showed the card:
   `forget_untrusted_memories`, no argument rows, `FORGET_CARD` as its text, Deny and Approve.
   Deny closed it, and about 10 s later the cortex called the tool again and the same card came
   back. Deny again ended the turn: "I was unable to forget the memories ... because the action was
   declined." Memory: 4 rows, all tainted. A clean turn in a new chat showed the second card
   too. The same night the dispatcher began to refuse a call identical to one the person declined
   in the same loop, with `ALREADY_DECLINED_MSG` and no card. In 13 Deny turns after that (5 on
   the overlay in new chats, 8 over `Converse` in 4 two-turn chats, one of them with no call) the
   cortex called the tool once per turn, so that refusal was not reached live.
3. **Typing after a card.** Words typed after pressing a card's button went nowhere: the button
   had the focus and went away with the card. Fixed the same night: the card's buttons no longer
   take the focus, and words typed after Deny reach the composer.
4. **Approve.** The same request again: recall returned one hit marked tainted, the card was the
   same, Approve ran it (`ok`, audit `trust=trusted`) and memory held 0 rows. The cortex then
   called `send_email` in the same turn without being asked; the turn had recalled a tainted
   row, so it returned `RECALL_DENIED_MSG`, and the reply told the person to ask to forget the
   memories, which they had just done, without saying the forget ran. The same night such a call
   began to return `RECALL_FORGOTTEN_MSG`; its rows are in
   [forget-untrusted-memories.md](forget-untrusted-memories.md#a-send-after-the-forget-in-the-same-turn).
5. **The send again**, as a new message in the same chat: recall returned no hit, the card showed
   `body`, `subject` and `to` as rows with the standard reason, Approve sent it to `<own>` with
   `trust=trusted` on the audit line, the reply said the email was sent, and memory held 1 row, not
   tainted.

Method: the drivers and the frames are in the run's scratch directory, not in the tree.
