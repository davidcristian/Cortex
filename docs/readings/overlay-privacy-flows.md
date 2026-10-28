# Readings: where a secret goes, through the brain and the overlay

Where sensitive text ends up when a person types it, asks the assistant to remember it, asks it to
forget it, deletes the chat that held it, or reads it from a file through the file tools, and what
a turn that fails mid-stream logs about it. The rule tested is the one in `AGENTS.md`: no secrets in
logs. A secret in a store that exists to hold the conversation is expected; a secret in a log line,
in a place a forget does not reach, or in text sent outside the turn is a defect. Memory and its
scopes are in [ADR-0008](../adr/ADR-0008-memory-v1.md), the chat delete and its memory cascade in
[ADR-0021](../adr/ADR-0021-session-read-rpcs.md), the file sidecar in
[ADR-0009](../adr/ADR-0009-tools-mcp.md).

## The rig

**2026-10-28**, the `cortexn9` GPU stack at the tree of that night: the resident cortex
(gemma-4-12B) at a context of 16,384 tokens, memory on pgvector with the default `global` scope,
the filesystem sidecar over a scratch root, Redis with `--appendonly yes`, the schedule backend
`none`. Turns ran over `Converse` from a host driver that names its own session, approves any
confirmation and prints one JSON line per turn, and one flow ran on the Linux shell
([body-overlay.md](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless)) on `Xvfb`. SM
clock at the flows: 0.60 of `clocks.max.sm`.

Every secret is synthetic: an API key shaped like `sk-test-...`, invented passwords, the public
test card number `4242 4242 4242 4242`. After each flow one script read every place a secret can
reach and counted it:

- `docker logs --since <flow start>` of all eight stack containers;
- every Redis key (`redis-cli --scan`, each value read by its type);
- `pg_dump --data-only --inserts` of the `cortex` database;
- the files the stack writes (the sidecar root, the backup directory), the shell's log, Vite's log
  and the WebKit data directory (`XDG_DATA_HOME`);
- the files on the Redis volume (`/data`).

## Where each secret was found

| Flow | Secret | Brain log | Sidecar log | Redis | Postgres | Redis volume | Shell files |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. typed in a turn | key, password | 0 | 0 | chat messages | 1 memory | AOF | n/a |
| 2. "remember ..." | wifi, card | 0 | 0 | chat messages | 2 memories each | AOF | n/a |
| 3. read from a file | 3 values | 0 | **1 line** | none | none | none | n/a |
| 4. turn that stalled | password | 0 | 0 | chat messages | none | AOF | n/a |
| 5. typed on the shell | locker code | 0 | 0 | chat messages | 1 memory | AOF | 0 |

The model host, the embedder, the subagent server, Postgres, Redis and the backup container logged
none of them. The brain's own log held none, including the error line and traceback of flow 4.

## 1. A secret typed in a turn

"My new API key is sk-test-... and my router admin password is Velvet-Otter-4418. Give me two
short tips on keeping them safe." The reply told the person to rotate both. The turn's text was
stored in the chat's `cortex:session:<id>:messages` list, which is expected, and also as one
`global` row in `memories` (`User: ... Assistant: ...`, with its embedding), because every
untainted exchange is recorded whether or not the person asked to remember it. A later chat that
asked "What do you remember about me? List everything." got both values back, together with the
card and wifi password of flow 2. An unrelated later turn (a welcome note for house guests) did
not name any of them.

## 2. Remember, forget, and delete the chat

"Remember that my wifi password is Plum-Lantern-9052." and the same for the card. Each reply
repeated the value and each exchange became one `memories` row. The "what do you remember" reply
listed every secret, and that exchange was itself recorded, so each value was in two rows after
one recall: a recall that names a secret copies it.

"Please forget my card number. Delete it from your memory completely." ended with the reply "I
have removed your card number from my memory." No tool ran. Both rows holding the card number were
still in `memories` afterwards. The cortex has no tool that deletes a chosen memory, so the reply
claimed a deletion that did not happen. Filed as
[918](../refinements/tasks/918-a-forget-asked-in-words-deletes-nothing-and-the-reply-says-it-did.md).

`DeleteSession` on all three chats removed their Redis keys. The `memories` rows stayed (two for
each secret), as ADR-0021 decides for the `global` scope, and a new chat asked "What is my wifi
password?" answered "Your wifi password is Plum-Lantern-9052." The overlay's confirm reads "Delete
this chat?", and nothing tells the person that what the chat taught the assistant stays. Filed as
[919](../refinements/tasks/919-a-deleted-chat-s-secrets-stay-in-memory-and-come-back-in-a-new-chat.md).

The deleted chats' text also stayed on the Redis volume. Redis writes every command to its
append-only file (AOF), and the router password of the deleted first chat was still in
`appendonly.aof.1.incr.aof` (197,688 bytes) after the delete; Redis rewrites that file only when it
has grown by 100% and is over 64 MB (`auto-aof-rewrite-percentage`, `auto-aof-rewrite-min-size`).
Filed as
[920](../refinements/tasks/920-a-deleted-chat-stays-in-the-redis-append-only-file.md).

## 3. A key file read through the file tools

A `deploy.env` in the sidecar root held a database URL with a password, a `STRIPE_SECRET_KEY` and
an `SMTP_PASSWORD`. "Read the file deploy.env and tell me which services it configures." ran
`list_allowed_directories`, `list_directory` and `read_text_file`, and the reply named the four
services without any value. The brain logged no value. The turn was tainted by the file read, so
no memory was recorded, and the chat's Redis list held no tool result.

The sidecar's own log held the whole file. `supergateway` logs every message between the brain
and the filesystem server at its default `--logLevel info`, so `docker logs` of the sidecar has a
`[supergateway] Child → StreamableHttp: {"result":{"content":[{"type":"text","text":"...` line
with every value. The file was 6 lines, so the result room's cut note did not apply. Filed as
[921](../refinements/tasks/921-the-file-sidecar-logs-every-file-it-reads.md).

## 4. A turn that stalls after a secret

"My bank login password is Indigo-Walrus-3317. Write a 400-word story about a lighthouse keeper."
The model host was frozen with `docker pause` 5 s into the turn and released after the brain
gave up. The turn ended after 124.9 s with the error event `inference_failed: llama-server sent
nothing for model 'cortex' for 120 s, the longest a stream may stay silent`. The brain logged
`inference failed mid-turn session_id=... turn_id=...` with a traceback, and neither held the
prompt. Nothing was recorded to `memories`. The chat's Redis list kept the user's message.

## 5. A secret typed on the Linux shell

A new chat on the overlay, the text "My locker code is Tangerine-Badger-5581, just keep it in
mind." typed and left unsent, the overlay hidden, then shown and sent. The unsent draft was found
in no file under the WebKit data directory, and neither was the sent text. The shell's log and
Vite's log held none. The overlay's header shows a new chat's first message as its title, so the
locker code was on screen in the header. The reply said "I'll keep that in mind for our
conversation"; the exchange was recorded as a `global` memory, which every later chat can recall.

## Not run

A reminder or scheduled task whose text holds a secret was not run: the stack ran the schedule
backend `none`, and switching it needs the brain recreated. The result room's cut note was not
reached, since the key file was short.
