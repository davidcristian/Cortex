# Readings: Redis, the brain and the cortex restarted under the Linux shell

What the overlay showed, what the store held and what the brain logged when Redis, the brain's
container or the cortex's `llama-server` was restarted or stopped while one chat was in use. The
procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless); a brain stopped
before a send or killed during a reply is in [overlay-turn-flows.md](overlay-turn-flows.md).

## The rig

**2026-10-10**, a debug build of the shell from the tree loading the overlay from Vite, WebKitGTK
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
- **Stopped across a reply's end.** Redis was stopped 0.8 s after a short question was sent and
  started again 22 s later. The overlay drew the whole answer, `Apple and banana.`, and under it a
  red bubble reading `session_store_unavailable: append to session '<id>' failed`. The dot stayed
  green throughout. The store held the question and no reply, so the chat shows the question
  unanswered when it is opened again, and the next turn's model input lacks the answer
  ([R-821](../refinements/tasks/821-a-reply-whose-append-fails-is-shown-and-not-kept.md)). The
  next question, sent after Redis was back, was answered and stored, with no restart of the shell.
  The ticker logged `schedule pass failed; the next poll retries` once per poll while Redis was
  down.

## The brain

- **Restarted between turns.** `docker restart` of the brain took 1.4 s and the dot stayed green
  at the frame after it. The next question was answered and stored in order. In this one turn the
  cortex thought for about a thousand tokens and answered the earlier question about the locker's
  wing instead of the bike lock code; asked again, it answered the code.
- **Restarted during a reply.** The brain was restarted 7 s into a 300-word essay. The model host
  logged `cancel task` 3 s after the signal, within the 5 s the server drains for. The overlay kept
  the text that had arrived, ending mid-sentence, and under it a red bubble reading
  `Unknown: h2 protocol error: error reading a body from connection`, which is what a `docker kill`
  shows. The dot went amber and then green. The old brain logged nothing about the cut turn. The
  store held the essay question and no reply, as for a stopped turn. The conversation stayed
  scrolled to the middle of the essay, with the error bubble below the visible part, until it was
  scrolled by hand ([R-819](../refinements/tasks/819-the-conversation-stopped-following-the-replies-of-one-chat.md)).

## The cortex process

- **Killed.** `kill -9` of the cortex's `llama-server` inside the model host container left the
  sidecar up: `GET /health` answered `ok` and `GET /models/cortex` answered `failed`, `the process
  exited with code -9`. Nothing started it again. The brain's `Health` stayed
  `ready=True detail='cortex-orchestrator 0.0.0'`, since with escalation off the brain holds no
  residency, and the dot stayed green
  ([R-820](../refinements/tasks/820-health-answers-ready-while-the-cortex-or-the-store-is-down.md)).
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
