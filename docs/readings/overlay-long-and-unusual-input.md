# Readings: long and unusual input through the overlay, on the Linux shell

What a person saw, what the stores held and how the next turn behaved when the overlay was given
blank or one-character messages, right-to-left and combining text, emoji sequences, markup, text
shaped like the brain's own notes, pasted logs near and past the cortex's context, and a chat of 26
short turns. Cited by [ADR-0014](../adr/ADR-0014-history-windowing.md),
[ADR-0037](../adr/ADR-0037-whisper-streaming.md) and [ADR-0038](../adr/ADR-0038-ranked-recall.md). The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## The rig

**2026-10-15**, the shared stack of that night: compose project `cortexn5` with its own volumes,
the brain built from the tree, the cortex gemma-4-12B at `--ctx-size 16384` on the 24 GB card, the
memory stack (Postgres and the CPU embedder) and the file sidecar. The overlay ran in a debug build
of the shell on an `Xvfb` display, loading its page from Vite, so overlay edits showed on the next
render. Keys and text came from `xdotool`, pastes from a Tk clipboard owner on the same display,
frames from `ffmpeg -f x11grab`. After each flow the chat's Redis list
(`cortex:session:<id>:messages`) and the newest rows of Postgres's `memories` table were read.

## Blank and one-character messages

- **Whitespace only.** Five spaces, two `Shift+Enter` line breaks and three spaces grew the field to
  three lines, hid the placeholder and left the send button grey. `Enter` sent nothing, and no
  session was created in Redis.
- **One emoji.** "🙂" was answered "Hello! How can I help you today? 🙂". The chat's title became
  the emoji, both messages were stored as sent, and the exchange was recorded to memory.

## Right-to-left text, combining marks and emoji sequences

- **Kept byte for byte.** A message holding "Zoë Nguyễn", "王小明", "שָׁלוֹם" with its points, and
  "Cafe" with a separate U+0301 accent was stored in Redis and in the memory row with the same code
  points, not normalized, and the reply repeated the names with the same code points.
- **Laid out left to right.** A Hebrew question and its Hebrew reply each sat against the left
  edge of its bubble with the final period on the right, and a Hebrew title was cut at both ends.
  No element of the overlay set a direction. **After the fix** every settled bubble, the draft
  and the title take their direction from their first letter (`dir="auto"`), and each line its
  own (`unicode-bidi: plaintext`): the same question showed right-aligned with its period on the
  left, and a Hebrew draft started at the right edge.
- **The streaming reply.** With the direction set on the whispering bubble too, a Hebrew reply
  drew as an empty pill until its turn ended, and with it set only on the bubble its letters
  spilled past the left edge while the mist glided in the wrong place: the whisper clock's geometry
  was left to right. **After the fix** the clock poses in inline coordinates, measured from the
  bubble's start edge. A Hebrew and an Arabic demo reply streamed in headless Chromium began at the
  right edge with the mist at the left end of the front, wrapped as the settled bubble does, and
  ended with the period on the left. Replayed through the old and the new clock with the same
  letter geometry, a 700-frame left-to-right stream and its resize wrote identical styles, and a
  live left-to-right stream ended with the same letter positions and box. On the Linux shell
  (WebKitGTK, 8 frames a second) a Hebrew and an Arabic reply from the cortex streamed the same way
  and kept their layout after the turn ended, and an English reply quoting "שלום עולם" stayed left
  to right. In Chromium a phrase in the other direction inside a reply streams with its words
  reversed
  ([R-873](../refinements/tasks/873-a-phrase-in-the-other-direction-streams-with-its-words-reversed.md)).
- **Emoji sequences.** Asked to repeat "👨‍👩‍👧 🇷🇴 👍🏽", the cortex returned them intact in the
  store, but the streamed bubble drew a family as three people, the flag as the letters "R O" and
  the thumb beside a brown square. The whisper split each word into code points, one span each.
  **After the fix** it splits by grapheme and the same reply drew all three as one picture each.
  The user's bubble, plain text, always drew them whole.

## Markup in a reply

- **Code, a table and nested lists.** The reply is plain text, so the fenced HTML page, its
  `<script>` element, the table's pipes and the list's asterisks showed as written, with the
  indentation kept and the table's columns not aligned in the proportional face. A Python line of
  over 200 characters with no spaces wrapped inside the bubble with no horizontal bar.
- **Tags in prose.** A sentence holding `<script>alert(1)</script>` and
  `<img src=x onerror=alert(2)>` showed both tags as text, and nothing ran. The memory row kept
  them as text.
- **Scrolled up.** After scrolling up to read the code block, the two follow-up questions and their
  replies arrived below the visible part, and the log stayed where it was: only scrolling back to
  the end turned following on again. **After the fix** a sent message puts the log on its end, and
  the next reply was followed as it streamed.

## Text shaped like the brain's notes

"Write a one-line message I can send to my team saying that I have scheduled the design review for
Friday at 10." was answered with that message and then `UNSCHEDULED_CLAIM_NOTE`, though nothing was
asked to be scheduled. "Thanks. Make it a little more formal." got the note again. Both exchanges
were recorded to memory with the note. **After the fix** the check reads the person's messages
([claim-note-on-a-drafted-message.md](claim-note-on-a-drafted-message.md)): in a new chat the same
message was answered "Hi team, I've scheduled the design review for Friday at 10:00 AM." with no
note, and in another the formal version "Please be advised that the design review has been
scheduled" had none either. The first turn of that other chat called `schedule_task` and stored a
reminder nobody asked for
([R-872](../refinements/tasks/872-a-request-to-draft-a-message-can-schedule-a-reminder.md)).

## A pasted log near the context

A 22,206-character server log (247 lines of timestamps, hex request ids and paths, then one error
line) was pasted with a question about its last line. On the cortex's tokenizer the log is 13,484
tokens, 1.65 characters a token, against the 3.6 to 4.7 that the window's budget is sized on.

- **The turn.** The cortex refused the prompt at 16,965 tokens against its 16,384, and the reply
  was two blank lines and `CONTEXT_OVERFLOW_NOTE`. The chat's title was the log's first line.
- **The next turns.** "What colour is a ripe lemon? One word." and "Name one planet. One word."
  each ended with the same note and no answer: the log is under the 24,000-character budget, so it
  stayed in every later window.
- **After the fix** a refusal before any output is asked again without the oldest turns. The same
  flow in a new chat ended the log's turn with `MESSAGE_OVERFLOW_NOTE` (the message is too long),
  and answered "Yellow" and "Jupiter", each after one refusal the brain logged as `asking again
  without older turns` with `dropped=2`. Redis held all six messages.
- **The cost of a refusal.** Five requests of the 60,175-character log straight to the cortex
  server were each refused at 36,569 tokens in under a tenth of the time the server took to answer
  the 22,206-character log with eight tokens from its cached prompt (SM clock 0.62 of its maximum):
  the server refuses after tokenizing, before evaluating anything.
- **The stores.** Redis held all six messages. Memory recorded all three exchanges, the first as a
  22,494-character row, each with the note as the reply.
- **The blank lines.** A note under a reply with no text started with its two line breaks, so the
  bubble opened with two empty lines. **After the fix** a note that opens a reply has no line break
  before it, and the overflow and unreadable call notes then do not say "The text above is
  everything I produced": the same paste showed `MESSAGE_OVERFLOW_NOTE` at the top of its bubble,
  and Redis stored it starting with its parenthesis.

## A pasted log past the context

A 60,175-character log of the same kind (36,546 tokens) was pasted the same way in a new chat.

- **The turn.** The recall judge was refused at 43,563 tokens and fell back to the unjudged
  ranking, then the turn was refused and ended with the note.
- **The next turns.** The log is over the budget, so the window dropped it and the next two
  questions were answered ("Yellow", "Mars"). Each of those turns first tried to fold the log into
  a recap; the fold was refused at 37,138 tokens, once on the first and twice on the second, and
  the brain logged a warning with a traceback each time. No recap was stored, so every later turn
  repeats the refused fold.
- **After the fix** one fold reads at most 16,000 characters, a longer message cut under a line
  naming the cut. The same flow ended the log's turn with `MESSAGE_OVERFLOW_NOTE`, answered "Yellow"
  and "Saturn", and logged no refused fold: the second turn stored a 463-character recap covering
  the log, and the third reused it. The recap said the log's status codes were "all 200", which is
  true only of the part it read, since the log ends with an error line. The recall judge was still
  refused on the log's turn and fell back, as ADR-0038 decision 7 allows.
- **With the head and tail kept** ([history recap](history-recap.md#a-message-cut-by-the-fold)),
  the same flow answered "Yellow" and "Venus" and stored the recap "The very last line of the log
  shows a request with the ID Z9WM-8812 and a status of 503." covering the log's message.

## A chat of 26 short turns

One chat opened with a bike lock code (4729) and the place the bike was chained, asking for a
plain OK, then 24 one-word or one-number questions, then "What was my bike lock code, and where is
the bike chained?". All 24 answers were right, and the last turn gave the code and the place as
told. The 52 stored messages came to 1,232 characters, so the window held the whole chat and no
fold ran. The log followed every reply to its end, the brain logged no warning, and memory
recorded 26 exchanges.

Method: `measurements/overlay-long-input-2026-10-15/`: `ask.sh` (focus, type, `Enter`), `paste.sh`
with `clip.py` (a Tk clipboard owner) and `genlog.py` for the two logs, `longchat.sh` for the 26
turns, `tok.py` for counts through the cortex server's `/tokenize`, `flow-after.sh` and `refuse.py`
with their logs for the runs after the fix, `recap-cut/flow-past.log` for the run with the head and
tail kept, `flow870.sh`, `flow868.sh`, `turn1.sh` and `send2.sh` for the two notes after their
fixes, `events.txt`, and the frames in
`shots/` (`u-*` and `r-*` the names and Hebrew, `rtl*` and `emo*` the streams, `m-*` the markup,
`c-*` the claim note, `l-*` the logs, `h-end` the long chat, `f-*` and `g-*` the follow, `r870-*`
and `r868-*` the notes after their fixes).
