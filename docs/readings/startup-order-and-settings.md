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
host's `GET /models/cortex`, polled once a second. No timing here is published as the card's
speed, so the SM clock was not read; a cortex load is named as one load, however long it takes.

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
- The turn still fails rather than waiting for the load, which
  [R-885](../refinements/tasks/885-a-question-sent-while-the-cortex-loads-ends-at-once.md) covers.

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
- The probe that failed at boot is never asked again, so this brain sends no trace budget for its
  whole life ([R-886](../refinements/tasks/886-a-brain-started-before-the-cortex-serves-never-sends-a-trace-budget.md)).
  The brain was restarted afterwards and logged `reads_budget=True`.

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
  named its environment variable. `confirm_names` appears in no compose file or runbook
  ([R-887](../refinements/tasks/887-a-malformed-setting-is-named-by-its-field-not-its-variable.md)).
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
`badcfg.sh`), their logs, and frames; the shell ran by the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).
