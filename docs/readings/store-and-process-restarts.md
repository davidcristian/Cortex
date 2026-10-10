# Readings: Redis, the brain and the cortex restarted under the Linux shell

What the overlay showed, what the store held and what the brain logged when Redis, the brain's
container or the cortex's `llama-server` was restarted or stopped while one chat was in use. The
procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless); a brain stopped
before a send or killed during a reply is in [overlay-turn-flows.md](overlay-turn-flows.md).

## The rig

**2026-10-10**, a debug build of the shell from the tree with the overlay embedded, WebKitGTK
drawing in software on an `Xvfb` display, against `docker/docker-compose.yml` with
`docker/docker-compose.gpu.yml` built from the tree under their own project name: the shipped
cortex, Redis with its append-only file on a named volume, escalation off and
`CORTEX_SCHEDULE_BACKEND=redis`. Keys and clicks came from `xdotool`, frames from
`ffmpeg -f x11grab`, the store from `redis-cli LRANGE` on the chat's message list, and the cortex's
state from the model host's `GET /models/cortex`. One chat was used throughout. It held three
complete turns, the first giving a bike lock code, before the first restart.

## Redis

- **Restarted between turns.** `docker restart` of the Redis container took 1.4 s. The next
  question was answered with the code from the first turn, and the chat held every question and
  reply once, in order. The brain logged nothing.
- **Restarted during a reply.** Redis was restarted 4 s into a 400-word essay. The essay streamed
  to its end, the dot stayed green, and the store held the question and the whole reply. The brain
  logged one `schedule pass failed; the next poll retries` from the reminder ticker.
- **Stopped for 21 s during a reply's thinking.** The cortex was still thinking when Redis came
  back, and the reply was stored after it. Nothing was lost.
- **Stopped across a reply's end, before the store retried.** Redis was stopped 0.8 s after a
  short question was sent and started again 22 s later. The overlay drew the whole answer,
  `Apple and banana.`, and under it a red bubble reading
  `session_store_unavailable: append to session '<id>' failed`. The dot stayed green throughout.
  The store held the question and no reply, so the chat showed the question unanswered when it was
  opened again, and the next turn's model input lacked the answer. The next question, sent after
  Redis was back, was answered and stored, with no restart of the shell. The ticker logged
  `schedule pass failed; the next poll retries` once per poll while Redis was down.
- **Appends during a restart.** A script in the brain's container appended to a scratch chat
  through `RedisSessionStore` every 50 ms for 12 s while Redis was restarted, five times. Each run
  had 8 or 9 appends fail at once with `SessionStoreError` over `Error 111 connecting to
  redis:6379`, a window of about 0.4 s, and every append after it succeeded. The client the adapter
  builds with `Redis.from_url` has connections with `Retry(NoBackoff(), 0)`, so nothing retries a
  refused connection. The scratch chats were deleted afterwards.

## Redis, with the session store's retry

**2026-10-10**, the same rig and chat after `RedisSessionStore` started calling Redis again for up
to 3 s after a refused, dropped or timed out connection, with a 1 s connect timeout
([the module doc](../modules/brain-session.md#redissessionstore)). Each run stopped Redis a
set time after a short question was sent and started it again by hand. The SM clock read 0.58 of
`clocks.max.sm` before the runs. The first two rows ran an earlier form of the retry.

Each row is one run. The times are from `docker stop` being sent and `docker start` returning to the
first try of the store call the outage met; a stalled try is one that ended in `Timeout connecting
to server`.

| Retry in the brain | Call met | Stop sent | Start returned | Failed tries | Result |
| --- | --- | --- | --- | --- | --- |
| 5 s of waits, no retry on a timeout, 5 s connect timeout | reply's append | 7.8 s before | 2.3 s after | 6 refused or unresolved | stored once |
| the same | question's append | 0.2 s before | 9.3 s after | 3 refused or unresolved, then one stall of 5.1 s | failed |
| 5 s from the first try, timeouts retried, 1 s connect timeout | question's append | 0.2 s before | 2.8 s after | 3 refused or unresolved, 2 stalls | stored once |
| the same | reply's append | 0.02 s before | 2.9 s after | 3 refused or unresolved, 2 stalls | stored once |
| the same | reply's append | 3.5 s before | 10.8 s after | 9, refused, unresolved or stalled | failed at 5.0 s |
| 3 s from the first try, the rest as above (shipped) | reply's append | 1.2 s before | 1.8 s after | 2 stalls | stored once |

- **A connect to a stopping container stalls.** For a short time after `docker stop` returns, a
  new connection to the container is neither refused nor accepted, before its name stops resolving
  (`Error -2`). With redis-py's 5 s connect timeout one such try took the question's append past
  its budget, and the turn ended before inference with only the error bubble shown and nothing of
  it stored. With a 1 s connect timeout the stall cost one or two tries of 1 s each.
- **Covered outages.** In each `stored once` row the overlay drew the reply with no error bubble,
  and the store held the question and the reply once each, in order. The brain logged one
  `a Redis call failed on its connection; calling it again after a wait` per failed try, with the
  wait and the error's type.
- **An outage past the budget.** The turn ended as before the retry: `Mount Everest and K2.` drawn
  above the `session_store_unavailable` bubble, and the question stored alone. The overlay's
  `ListSessions` that followed was still retrying when the body's 5 s call deadline ended it, and
  the brain logged `the caller stopped waiting; this call was abandoned mid-flight`. The shipped
  budget is 3 s for that reason, under the deadline with room for one stalled try.

## The brain

- **Restarted between turns.** `docker restart` of the brain took 1.4 s and the dot stayed green
  at the frame after it. The next question was answered and stored in order. In this one turn the
  cortex thought for about a thousand tokens and answered the earlier question about the locker's
  wing instead of the bike lock code; asked again, it answered the code.
- **Restarted during a reply.** The brain was restarted 7 s into a 300-word essay. The model host
  logged `cancel task` 3 s after the signal, inside the 5 s grace the server stopped with then. The
  overlay kept the text that had arrived, ending mid-sentence, and under it a red bubble reading
  `Unknown: h2 protocol error: error reading a body from connection`, which is what a `docker kill`
  shows. The dot went amber and then green. The old brain logged nothing about the cut turn. The
  store held the essay question and no reply, as for a stopped turn; the cut and its fix are in the
  [next section](#a-turn-in-flight-when-the-brain-stops). The conversation stayed scrolled to the
  middle of the essay, with the error bubble below the visible part, until it was scrolled by hand
  ([cause and fix](#following-a-reply-cut-by-a-restart)).

### A turn in flight when the brain stops

**2026-10-10**, the same rig. `docker restart cortexn2-brain-1` was sent 1 s after the first words
of a 900-word essay showed, and `docker events` gave the signal times.

- **Before** (the server stopping with a 5 s grace and no `stop_grace_period`). The daemon sent
  signal 15, then signal 9 3.0 s later, and the brain exited with 137, inside its own grace. Docker
  Desktop's daemon stops a container that sets no stop timeout after 3 s: a scratch container whose
  PID 1 ignores SIGTERM took 3.1 s to `docker stop`, and 10.3 s with `--stop-timeout 10`. A Python
  client on its own `Converse` saw `UNAVAILABLE` `Stream removed (Socket closed (GOAWAY received;
  Error code: 0; Debug Text: Server shutdown))` 3.06 s after the restart command, and the model
  host logged `cancel task` 6 ms later. The overlay showed the h2 error above, and the store held
  the question alone.
- **After** (a 3 s drain, then `ConverseStream.shut_down`, and `stop_grace_period: 10s`), two runs.
  The brain logged `ending a turn because the brain is stopping` with the session and turn ids
  3.00 s after signal 15, the model host logged `cancel task` 8 ms later, and the brain exited with
  0 0.8 s after that, with no signal 9. The overlay kept the text that had arrived, ending mid-word, and under it
  a red bubble reading `brain_stopping: the brain is shutting down, so this reply was cut short; ask
  again once it is back`; the log followed it to the end. The store held the question alone.

## Following a reply cut by a restart

**2026-10-10**, the same rig, with a page build that also drew a line at the top of the window for
each scroll event of the log and each follow call of `overlay/useLogScroll.ts`: `scrollTop`,
`scrollHeight`, `clientHeight` and the follow flag. The brain's container was restarted during a
900-word essay, 12 s after the send in the run before the fix and 1 s after the first words showed
in the runs after it, which a poll of the frames found, so the 5 s drain cut the reply in the middle
([R-819](../refinements/tasks/819-the-conversation-stopped-following-the-replies-of-one-chat.md)).

- **Before the fix.** The rest of the received text and the error bubble arrived in one render
  that made the content 545 px taller. A scroll event then fired with the box still at
  `scrollTop` 6701, where the last follow call had put it, and the hook read the 545 px gap as the
  reader leaving the end: the flag went off, and the follow call 10 ms later did nothing. The log
  stayed on the first lines of the reply. The event was the one the engine queues after each
  position the hook writes, dispatched after the render rather than before it.
- **After the fix.** A scroll event turns following off only when the box has moved from where the
  hook last put it or last saw it. Two runs cut mid-reply ended with the log on the error bubble;
  the follow call after the render moved the box 698 px and 764 px. In neither run did the queued
  event fall between the render and the follow call, so the rule itself is shown by the Vitest
  cases in `overlay/useLogScroll.test.tsx`, which fail on the old rule.
- **Cut before the first words.** In four runs, two on each side of the fix, the restart came
  while the cortex was still thinking; the error bubble arrived alone and the log followed it. A
  300-word essay restarted 7 s in finished inside the drain and ended normally, on its end.
- **Hidden and shown while a reply streamed.** The summon chord hid the panel 6 s into a 500-word
  essay and showed it 3 s later, before the fix: the log stayed on its end and no scroll event
  cleared the flag. The 2026-10-07 path, an `Enter` typed into the hidden window, was not run.
- **A fresh shell, before.** Each of six starts of the shell opened the restored chat one to three
  messages short of its end, with the flag still set. Three more starts, with a page build that also
  drew each size change of the box, showed the same sequence each time. The hidden window lays the
  log out 10 px tall and 20 px wide, and the follow calls put it on its end. The summon gives the
  window its 640 by 720 size, and the box is 477 px tall and still on its end. Then the panel places
  its own height: the view goes from 632 px to 545 px and the box from 477 px to 390 px, with
  `scrollTop` unmoved, which leaves 87 px of the log under the composer. No scroll event and no
  follow call came after it.
- **A fresh shell, after.** `useLogScroll` observes its box and follows a change in its size while
  no roll runs in the column. In four starts the observer's follow call moved the box 87 px and the
  last message stood above the composer. The switcher opened and shut on that log left it on its end.

## The cortex process

- **Killed.** `kill -9` of the cortex's `llama-server` inside the model host container left the
  sidecar up: `GET /health` answered `ok` and `GET /models/cortex` answered `failed`, `the process
  exited with code -9`. Nothing started it again. The brain's `Health` stayed
  `ready=True detail='cortex-orchestrator 0.0.0'`, since with escalation off the brain held no
  residency and `Health` read nothing else, and the dot stayed green. With the serving watch the
  dot turns amber instead ([below](#health-and-the-dot)).
- **A turn while it is down.** The question ended at once in a red bubble reading
  `inference_failed: llama-server request failed for model 'cortex'`. The brain logged
  `inference failed mid-turn` with the session and turn ids. The store held the question and no
  reply.
- **Brought back by an operator.** Step 2 of
  [the swap recovery runbook](../runbooks/model-swap-recovery.md), a `POST /models/cortex/start`
  through `compose exec model-host curl`, answered `loading` at once; `GET /models/cortex` was
  polled every second until it answered `ready`. The same question sent next was answered and
  stored, with no restart of the shell, the brain or the model host. This is the state
  [R-310](../refinements/tasks/310-a-pass-that-starts-the-cortex.md) names.
- **A brain restart does not bring it back.** The cortex was killed again and the brain's
  container restarted. The brain logged `trace budget probe failed` and served `ready=True`, and
  `GET /models/cortex` still answered `failed` a minute later. The same `POST` then brought it back,
  and the next question was answered.
- **Started again by the model host.** With the sidecar restarting a cortex that exits unasked
  ([ADR-0054](../adr/ADR-0054-baseline-residency.md) decision 9), `GET /models/cortex` was read
  and `Health` called once every 1.4 s from the kill. It read `failed`, `the process exited with
  code -9` at 1.5 s, `loading` with a new pid at 2.9 s and `ready` at 44 s, as long as the
  operator's start above took; the sidecar logged `a model process exited without being asked to;
  starting it again` with `attempt=1 code=-9`. `Health` read `not answering` and then `still
  loading` until the cortex was `ready`. Run twice; in the second the dot was amber on a summon 8 s
  after the kill and green 61 s after it, and `Name two islands, one line.` was answered with no
  operator step.

## Health and the dot

**2026-10-10**, the same rig after `Health` started reading a `ServingWatch` that asks the cortex's
`GET /health` and sends Redis a `PING` every 2 s, each within 1 s
([ADR-0054](../adr/ADR-0054-baseline-residency.md) decision 8). `Health` was called once every
0.6 s from inside the brain's container, and the dot was read by hovering it for its tooltip. The SM
clock was not read, since nothing here was timed against the card.

| Event | `Health` after it | The dot |
| --- | --- | --- |
| `kill -9` of the cortex's `llama-server` | `ready=False`, `the usual assistant's model server is not answering, so a turn cannot be answered`, from the third call, 1.6 s after the kill | green until the overlay probed: amber after a summon, or after a question ended in `inference_failed` |
| `POST /models/cortex/start` | `the usual assistant is still loading` from 1.0 s after the start, for the 41 to 44 s each load took | amber, the tooltip reading `The brain is not serving: the usual assistant is still loading` at its 5 s recheck |
| the cortex `ready` | `ready=True detail='cortex-orchestrator 0.0.0'` | green at the next 5 s recheck |
| `docker stop` of Redis | `the conversation store is not answering, so a turn cannot be saved` from the first call, 0.3 s after the stop returned | amber after a summon, reading `the conversation store did not answer within 1 s` |
| `docker start` of Redis | `ready=True` 1.6 s after the start returned | green at the next 5 s recheck |

- **Run four times for the cortex, once for Redis.** Every cortex run read the same two faults in
  the same order. The brain logged `a part a turn needs is not answering` with the fault once per
  change of fault, and `every part a turn needs is answering again` once at the end of each outage;
  nothing else, since the cortex check sends on the transport and not through a client that logs
  each request.
- **Two faults for one Redis outage.** A `PING` was refused or failed to resolve the name, which
  reads as `not answering`, or stalled for the whole second, which reads as `did not answer within
  1 s`, and the reading moved between the two during the outage. Both are accurate.
- **With escalation on.** The same stack with `CORTEX_ESCALATION=1`, the supervisor backend and
  the deep tier in the roster, where the cortex probe asks only between handoffs. A `kill -9` of the
  cortex read `not answering` at 1.5 s and `still loading` from 4.3 s, until `ready` at 44.5 s,
  while the residency report said serving. No handoff was run, so a reading dropped across one was
  checked by the unit tests alone.
- **An open, green dot is not polled.** With the overlay on screen and green, killing the cortex
  left the dot green until the overlay was summoned again or a turn ended, as the overlay's link
  hook is written to do.
