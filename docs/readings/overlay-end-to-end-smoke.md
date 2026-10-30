# Readings: an end to end smoke flow on the Linux shell

One chat on the overlay that touches each path the night's brain fixes changed: a request to
remember, a recall, a forget with its card, a reminder delivered to the overlay, and a question
beside a file tool request. The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## The rig

**2026-10-30**, the debug shell loading the overlay from Vite on `Xvfb`, driven with `xdotool`,
one frame grabbed after each step. The stack is the shared test stack of that night: gemma 12B as
the cortex at context 16,384, the file sidecar rooted at `/projects` holding `notes.txt`, the
pgvector memory with the default `global` scope, and schedules on Redis in `Europe/Berlin`. The
brain was built from the tree that holds the request reader's verbs ("erase", "get rid of",
"note") and the wider reminder words of `unasked_tools.py`. `memories` was empty and no schedule
key existed at the start. After each step the rows of `memories` and the `cortex:schedule*` keys
were read with `psql` and `redis-cli`. SM clock after the flow: 0.60 of `clocks.max.sm`.

## The flow

| Step | Message | What the overlay showed | Store after it |
| --- | --- | --- | --- |
| 1 | "Please remember that my locker code is 4827." | "I've noted that your locker code is 4827." | one row; the turn also called `forget_memories` twice, both matched nothing |
| 2 | "What is my locker code?" | "Your locker code is 4827." | two rows |
| 3 | "Please forget my locker code." | a `forget_memories` card with `text` `4827` listing both rows; after Approve, "I've forgotten your locker code." | no row |
| 4 | "Remind me in two minutes to stretch." | "OK. I've set a reminder to stretch in two minutes." | one row; one `cortex:schedule:` key, due 120 s after the call |
| 5 | "What is the capital of Portugal? Also, list the directories you are allowed to access." | Lisbon, then ten folders that do not exist | two rows |

- **Step 1.** Both forget calls matched nothing and the message asks to remember, so the turn was
  recorded, as decision 5 of
  [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md) states. The calls themselves are the
  subject of [R-952](../refinements/tasks/952-withheld-unasked-tools-may-raise-forget-calls-on-a-remember-request.md).
- **Step 2.** The recall was in the same chat, so the chat's own history held the code as well
  as the stored row.
- **Step 3.** The card listed both stored exchanges. The turn deleted them and stored nothing,
  and the reply had no note, since its forget call deleted rows.
- **Step 4.** The reminder fired on time. The push failed, as on every `Xvfb` run, because no
  notification server is on the shell's session bus (`push failed; pull will deliver`), and the
  item moved to `cortex:schedules:deliverable`. The open panel showed nothing: `useReminders`
  pulls on the rising edge of visibility, so the card "stretch", "open chat", "1m ago" showed
  only after the panel was hidden and summoned again. "open chat" opened the flow's chat and did
  not ack the reminder; its check button did, after which no `cortex:schedule*` key was left.
- **Step 5.** The reply repeated no sentence. The cortex made no tool call: the audit has no
  `list_allowed_directories` line for the turn, and the reply named `/home/user/Documents` to
  `/home/user/Work`, while the sidecar's one folder is `/projects`. The untainted exchange was
  stored.

## The same message in fresh chats

Two fresh chats on the overlay right after the flow, with the flow's rows still stored.

- **The first** called `list_allowed_directories` and replied "/projects". The turn read tool
  output, so it was tainted and not recorded.
- **The second** made no call and replied with the same ten folders in the same order as the row
  step 5 stored, which its recall could read, and stored them again. That the reply came from the
  recalled row is an inference from the identical list; no recall trace was read.

An answer written with no call became a stored fact that a later chat repeated;
[file-request-without-a-call.md](file-request-without-a-call.md) measures it, with the check that
records no such turn.
Every row the flow stored was deleted afterwards.
