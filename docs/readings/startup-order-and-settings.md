# Readings: the stack started in an unusual order or with a wrong setting, on the Linux shell

What the person and the operator saw when the model host or the brain started while the other was
down or still loading, when the shell held a token the brain does not accept, and when the brain
started with a malformed setting. Restarts of a running Redis, brain and cortex are in
[store-and-process-restarts.md](store-and-process-restarts.md), and a shell started before the
brain in [overlay-session-resume.md](overlay-session-resume.md).

## The rig

**2026-10-16**, the shared stack of that night: compose project `cortexn6` with the GPU, model
host loopback, memory and tools files, escalation on with the supervisor backend, the shipped
gemma-4-12B cortex, and the Linux shell's debug build on an `Xvfb` display. Keys and clicks came
from `xdotool`, frames from `ffmpeg -f x11grab`, chats from Redis, and states from the model
host's `GET /models/cortex`, polled once a second. The flows name a cortex load as one load,
however long it takes; the one timing published, the load itself, is below with its SM clock.

Each flow's question was written down before it ran.

## A question sent while the cortex loads

Question: after `docker restart` of the model host, what does a question sent through the overlay
during the cortex's load show, and does the stack recover with no operator step?

- In both runs the cortex read `loading` from the restart until one cortex load later, then
  `ready`, with no operator step and no brain restart.
- **Before the fix.** The question ended at once in a red bubble quoting the server:
  `inference_failed: llama-server answered 503 for model 'cortex': {"error":{"message":"Loading
  model","type":"unavailable_error","code":503}}`. The dot went amber and was green again after
  the load. The brain logged a traceback ending in that `InferenceError`, then the serving watch's
  `the usual assistant is still loading`. The store kept the question alone.
- **After the fix**, which reads that 503 as a model still loading, the same run showed
  `inference_failed: model 'cortex' is still loading, so it cannot answer yet; ask again once it
  is ready`.
- **After the wait was added** (`CORTEX_INFERENCE_LOAD_WAIT_S`, default 120 s), the same run
  showed the chip `waiting for the model to finish loading` under the question from the first
  second, logged `the model is still loading; the turn waits for it`, and answered `Nile, Amazon`
  0.96 of one median cortex load after the question, with no red bubble and nothing sent again by hand.
- **Stop during the wait.** The same restart, a question, and the Stop button 10 s later: the chip
  went at once, the store kept the question alone, and nothing was answered once the cortex was
  `ready`.
- **A server that is down** still fails at once: with the model host stopped, the question below
  ended in `llama-server request failed` within a second.

## How long a cortex load takes

Question: how long does a model host restart keep the cortex refusing requests, and what bound
covers it? The answer sizes `CORTEX_INFERENCE_LOAD_WAIT_S`; a null result would be a load too
variable to bound from three runs.

- Three `docker restart` runs of the model host with the shipped gemma-4-12B cortex, the model
  file read from the `/models` mount, polling `GET :8080/health` and `nvidia-smi --query-gpu=
  clocks.sm,clocks.max.sm,utilization.gpu,memory.used` every half second.
- llama-server answered 503 from 0.11 of the restart-to-ready time on, and 200 at 0.35, 0.35 and
  0.36 of the 120 s bound after the restart command. The SM clock read 0.58 to 0.62 of its maximum and utilization
  0 throughout, and the card's memory rose only in the last second: the load is bound by reading
  the model file, not by the card, so a slower model drive, not a slower card, lengthens it.
- The bound is 120 s, about 2.9 times the median load. A turn that outlasts it ends with the
  loading message it ended with before the wait existed.

## The brain started while the model host is stopped

Question: does a brain started with no model host crash, loop or serve, what does a question
show, and does the brain recover when the model host comes up?

- With the model host stopped, `docker restart` of the brain gave a healthy container on its
  first healthcheck, with no restart. It logged that the model host could not be asked for its control bounds, that
  the trace budget probe failed with `Name or service not known`, and a traceback for failing to
  clear the deep model at boot, then `gRPC server listening`.
- A question sent next ended in `inference_failed: llama-server request failed for model
  'cortex'`, with the dot amber; the store kept the question alone.
- `docker start` of the model host gave a `ready` cortex one load later, and the same question was
  answered (`Lake Superior and Lake Victoria.`) with no brain restart.
- **Before the fix** the probe that failed at boot was never asked again, so that brain sent no
  trace budget for its whole life; a restart afterwards logged `reads_budget=True`.
- **After the fix**, the same order (the image built from the fix, same stack) logged `trace budget
  probe failed; asking again before the next request` once at boot with `Name or service not known`.
  A question sent before the model host started ended at once in `inference_failed: llama-server
  request failed for model 'cortex'`, and the probe asked again before it without a second warning.
  Once the cortex was `ready`, the next question's request was preceded by `trace budget probe
  answered reads_budget=True`, and the reply (`Lake Superior and Lake Michigan`) came with no brain
  restart.

## A shell with a token the brain does not accept

Question: what does the person see when the shell's `CORTEX_SEAM_TOKEN` differs from the brain's?

- The shell started and bound its `BodyService` as usual. On the first summon the dot was amber,
  and its tooltip read `The brain is not serving: Unauthenticated: invalid or missing token`. The
  panel opened on `New chat`, since the chat list could not be read.
- A question ended at once in a red bubble reading `Unauthenticated: invalid or missing token`,
  and nothing was stored. Neither the brain nor the shell logged the refused call.
- Accepted as is: the words name the cause, and the token is not printed anywhere. On this `Xvfb`
  display the native tooltip was cut at the window's right edge.

## A malformed setting at the brain's start

Question: does a brain given one malformed setting stop with an error that names the variable,
without printing a secret? Each case ran as a one-off `docker compose run --rm --no-deps -T -e
<setting> brain`, which publishes no port, under a 45 s `timeout`.

| Setting | Exit | Last line of the error |
| --- | --- | --- |
| `CORTEX_TOOLS_GATED=[read_text_file` | 1 within 2 s | `SettingsError: error parsing value for field "confirm_names" from source "EnvSettingsSource"` |
| `CORTEX_SCHEDULE_TZ=Mars/Olympus` | 1 within 2 s | `ValidationError` for `ScheduleConfig` `tz`: `unknown timezone 'Mars/Olympus'` |
| `CORTEX_SEAM_PORT=23o51` | 1 within 2 s | `ValidationError` for `RpcServerConfig` `port`: not a valid integer |
| `CORTEX_REDIS_URL` with a port `63x79` | 1 within 2 s | `ValueError: Port could not be cast to integer value as '63x79'` |
| `CORTEX_REDIS_URL` whose password holds a `/` | 1 within 2 s | `ValueError: Port could not be cast to integer value as '<the password before the slash>'` |

- Every case stopped the brain before it served, with a traceback of about 48 lines, and none
  named its environment variable. `confirm_names` appears in no compose file or runbook.
- **After the settings reader.** The same first four settings, run from the working tree with
  `python -m cortex_orchestrator` on 2026-10-16, each ended with exit 1 and one line, for example
  `ERROR:cortex_orchestrator.entry:setting refused reason="CORTEX_SCHEDULE_TZ: unknown timezone
  '<value>'"`, the confirmed tools as `CORTEX_TOOLS_GATED is not valid JSON` and the port as
  `CORTEX_SEAM_PORT: Input should be a valid integer`. No value appeared in the output.
- **The Redis password.** The Redis client reads the text before the slash as a port and prints
  it, which is the defect the memory DSN's check already prevents. With the same check on
  `CORTEX_REDIS_URL`, the run ended in `RuntimeConfigError: CORTEX_REDIS_URL has an authority the
  Redis client cannot read; percent-encode any password character that would end a URL's
  authority`, and the password's text appeared nowhere in the output.

## The host's zone through the stack recipes

Question: does the zone `docker/host-zone.sh` reads reach the brain under `cortexn6`, and does
the brain's log name it?

- `docker/host-zone.sh` printed `Europe/Berlin`. `docker compose config brain` showed
  `CORTEX_SCHEDULE_TZ: UTC` with the variable unset and `Europe/Berlin` with the recipes' form,
  `CORTEX_SCHEDULE_TZ="${CORTEX_SCHEDULE_TZ:-$(sh docker/host-zone.sh)}"`.
- The brain recreated with that form read `Europe/Berlin` from `printenv` and resolved it to a
  `zoneinfo` zone. Its log named no zone until the startup line `scheduling is on` was added; it
  now logs `zone=Europe/Berlin`, and `zone=UTC` after the stack's own setting was restored.

Method: `measurements/startup-order-2026-10-16/`, with the flow scripts (`f3.sh`, `f4.sh`,
`badcfg.sh`, and `loadtime.sh` and `stop.sh` in `fix/`), their logs, and frames; the shell ran by the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).
