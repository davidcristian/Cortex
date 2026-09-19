# Host-side work

Every piece of work only the host's own hardware can perform, one file per item in
[tasks/](tasks/). This is the companion to [refinements/](../refinements/index.md), and the two
hold different kinds of not-done:

- **[refinements/](../refinements/index.md) holds deferred *design*.** Work anyone can pick up
  once an interface, a consumer, or a decision unblocks it. Its tasks describe code that is not
  written.
- **This directory holds work blocked on hardware the dev machine does not have.** The code is
  written; what is missing is a machine that can run it. Almost every item here is a *validation*,
  and the one that is not, the overlay polish pass, says so in its own file.

Neither is "host-only" in the [AGENTS.md](../../AGENTS.md) sense. An `integration`-marked live
test is host-only because it needs Docker, a GPU, or a network service, and the engineering
contract is explicit that "on the host" **includes the agent**: those run here, in this repo, by
whoever is working. An item goes in this directory only when the agent's dev machine physically
cannot do it.

## How to work this backlog

The layout and its reasoning are [ADR-0039](../adr/ADR-0039-backlog-per-task.md); the mechanics
match [refinements/](../refinements/index.md), with one difference in the status grammar and one in
what happens at the end.

**The statuses differ because a check is not a design.** A refinement is done or declined; a host
check can be attempted, inconclusive, and worth retrying. So an item here reads `never attempted`
(the default), `attempted <date>, inconclusive: <what happened>`, or `done <date>`. An environment
problem is not a failed check, and recording it as inconclusive is the accurate outcome.

**A `**Verified:**` line means the same here as there.** It holds the day somebody last checked an
item's claim against the code, which is the half a reading can settle: the built code keeps moving
while the hardware it needs stays out of reach, so the description a session starts from can be
months behind the tree, and the date says how far. The hardware half is what
`attempted <date>, inconclusive:` records. An ongoing item may have no date, because it never
closes and so has no single reading a session would start from.

**The exit contract differs too.** An item that completes writes its reading into the readings
record under [docs/readings/](../readings/README.md) that its decision rests on and into its
runbook, edits its origin decision record in place wherever the run changed what that record
states, then stops being work. A refinement's text often corrects its own ADR and so is kept in
place; a host check produces a *measurement*, whose home is a readings record and the runbook, so a
completed item's file shrinks to a heading, its status and a pointer. Emptiness here matters: the
ROADMAP's finish line requires every slice, this directory, and the refinements backlog all being
clear.

Two qualifiers the first exits produced. **A completed item keeps its number for as long as
anything still points at it**, and its file is not deleted, because four items in the GPU session
are written against "item 1". And **an item that owes a procedure exits by writing the procedure,
not by describing it**: the injection-harness run's four warnings about how the harness fails were
its most reusable content, so they left for
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) with the measurement rather than staying in
a completed section where nobody re-running the row would find them.

After any change here, run `just backlog` to regenerate the section below, and commit it with the
task file. `just check` fails if you forget.

## The two capabilities

Every item has one of these two tags or both, and mixing them wastes a session:

| Tag | What it means | Why the dev machine cannot stand in |
| --- | --- | --- |
| **W** | A real Win32 desktop session, where the body runs natively | The dev machine is Linux under WSL2. Nothing OS native (COM, WinRT, GDI, a real Tauri IPC hop, a real window) exists to exercise. |
| **G** | A card that holds the real model tiers (24 GB) | **Nothing, since 2026-08-04.** See the correction below: the development card holds the tiers, so a G item is agent-runnable. |

**The G premise was false.** This table first said the dev GPU is an 8 GB card, so that no tier
pair, no 31B model and no GPU-placed subagent beside a resident cortex was reachable.
[ADR-0030](../adr/ADR-0030-brain-handoff.md) did measure `gemma-4-12b-it-qat-q4_0.gguf` alone taking
7715 of that card's 8188 MiB, and every figure derived from that card stays true of it. What failed
is the premise underneath: that the 8 GB card is the card the repo is developed on. On 2026-08-04
the development machine reported 24463 MiB and ran the deep-model pick end to end, loading and
serving all four candidates alone on the card. **So G on its own is no longer a reason to file work
here.** [AGENTS.md](../../AGENTS.md) is explicit that "on the host" includes the agent and that GPU
and model behavior reachable through Docker is done now rather than deferred.

Two things this does **not** change. **W is untouched**, and it is now the only tag doing real work
here: a Win32 desktop session is still something no agent can stand in for. And **the three W+G
items are still blocked**, on their W half alone. Those are the tier-scale swap, the chaos kill
during one, and the timings of one: a handoff begins only when the confirm card in front of
`escalate_to_brain` is approved, that card is a `ConfirmRequest` on the Converse stream, and the
only shipped client that answers one is the overlay. Marked 2026-07-19 after an audit tried to
execute them from the GPU doc alone.

**The tag was also withdrawn from two items that did not need it**, on 2026-07-19: a fully
cortex-driven `set_volume` and the end-to-end answer on the capture path. Both had been marked W+G
on an older sentence saying the 12B cortex does not fit 8 GB, which
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md) had already measured false on 2026-07-17: at
`--ctx-size 4096 --parallel 1` the cortex fits the dev GPU **beside its projector**, and it drove a
real vision turn there on 2026-07-18. Both items are therefore **W**. The tag matters in both
directions: a W+G item is one nobody should start until both capabilities are in the room, and if
the Windows host and the 24 GB card turn out to be two machines, a wrong tag costs exactly the trip
the tagging exists to prevent.

**Tagged by capability, not by machine name, deliberately.** The repo's own evidence says the
Windows host and the 24 GB card are one laptop: [ARCHITECTURE.md](../ARCHITECTURE.md) says "Three
tiers share one 24 GB GPU" and [ADR-0004](../adr/ADR-0004-model-lineup.md) says "First real
bring-up on the 24 GB card". But **no document states it**, so the layout does not assume it. A
capability tag is correct whether that is one desk or two.

## An item's expected outcome is a hypothesis

The refinements index warns that a task's own *cost* estimate is a hypothesis. Here the analogue is
different: an item's own *predicted result* is a hypothesis, and this repo has been wrong about one
more than once. [ADR-0012](../adr/ADR-0012-resource-governance.md) predicted a CUDA OOM path that
the shipped re-place deliberately did not build;
[ADR-0023](../adr/ADR-0023-body-gateway-volume.md) recorded `CaptureScreen` as behind the same
interface and it cost five proto fields plus a port method. So the "Pass looks like" lines in these
files are what the design expects, not what will happen. When a run contradicts one, the run wins
and the ADR is edited to state what the run found. That correction is the most valuable thing a
session produces.

<!-- backlog:begin (generated by `just backlog`; edit the task files, not this block) -->

**18 open, 2 ongoing, 3 closed, 23 in total.**

## What remains

### Never attempted (18)

- **[H-001](tasks/001-bring-up-and-streamed-turn.md)** The bring-up: hotkey, tray, and a streamed turn (windows-desktop).
- **[H-002](tasks/002-core-audio-volume-action.md)** The real Core Audio volume action (windows-desktop).
- **[H-003](tasks/003-real-reminder-toast.md)** A real reminder toast (windows-desktop).
- **[H-004](tasks/004-confirm-card-over-ipc.md)** The confirm card through real Tauri IPC (windows-desktop).
- **[H-005](tasks/005-session-read-commands.md)** The session-read Tauri commands (windows-desktop).
- **[H-006](tasks/006-preference-commands-across-restart.md)** The preference Tauri commands across a restart (windows-desktop).
- **[H-007](tasks/007-reminder-pull-surface.md)** The reminder pull surface on the hotkey path (windows-desktop).
- **[H-008](tasks/008-connection-indicator-ipc-hop.md)** The connection indicator's real IPC hop (windows-desktop).
- **[H-010](tasks/010-pgdata-on-windows-drive.md)** PGDATA directly on the Windows drive (windows-desktop).
- **[H-012](tasks/012-display-capture-path.md)** The whole-display GDI capture path (windows-capture).
- **[H-013](tasks/013-focus-target-capture.md)** The focus-target capture and its Z-order walk (windows-capture).
- **[H-014](tasks/014-os-window-polish.md)** The OS-window half of the overlay polish (overlay-polish).
- **[H-015](tasks/015-completion-chime.md)** A soft completion chime (overlay-polish).
- **[H-016](tasks/016-live-region-speech.md)** What the live region is spoken as (overlay-screen-reader).
- **[H-018](tasks/018-tier-scale-swap.md)** The tier-scale cortex to brain swap (gpu-tier-scale).
- **[H-019](tasks/019-chaos-kill-tier-scale.md)** The chaos kill at tier scale (gpu-tier-scale).
- **[H-020](tasks/020-measured-swap-timings.md)** Measured swap timings (gpu-tier-scale).
- **[H-023](tasks/023-cgroup-cap-numbers.md)** The cgroup cap numbers (gpu-tier-scale).

## Ongoing, never closes (2)

Neither work that remains nor work that finishes: an observation made over time, or an obligation on every change. They are counted apart so that neither number is wrong.

- **[H-009](tasks/009-unbalanced-com-initialization.md)** Unbalanced COM initialization on the blocking pool (windows-desktop): an observation to make over months of real use, never a check that passes.
- **[H-011](tasks/011-toolchain-linked-full-build.md)** The toolchain-linked full build (windows-desktop): an obligation on every change to these trees, not a check to run once.

## Every task, by session

### gpu-tier-scale

4 open of 7.

- [H-017](tasks/017-deep-model-pick.md) The deep-model pick. done 2026-08-04.
- [H-018](tasks/018-tier-scale-swap.md) The tier-scale cortex to brain swap. never attempted.
- [H-019](tasks/019-chaos-kill-tier-scale.md) The chaos kill at tier scale. never attempted.
- [H-020](tasks/020-measured-swap-timings.md) Measured swap timings. never attempted.
- [H-021](tasks/021-injection-harness-run.md) The 31B injection-harness run. done 2026-08-04.
- [H-022](tasks/022-gpu-placed-subagent.md) A GPU-placed subagent beside a resident cortex. done 2026-08-04.
- [H-023](tasks/023-cgroup-cap-numbers.md) The cgroup cap numbers. never attempted.

### overlay-polish

2 open of 2.

- [H-014](tasks/014-os-window-polish.md) The OS-window half of the overlay polish. never attempted.
- [H-015](tasks/015-completion-chime.md) A soft completion chime. never attempted.

### overlay-screen-reader

1 open of 1.

- [H-016](tasks/016-live-region-speech.md) What the live region is spoken as. never attempted.

### windows-capture

2 open of 2.

- [H-012](tasks/012-display-capture-path.md) The whole-display GDI capture path. never attempted.
- [H-013](tasks/013-focus-target-capture.md) The focus-target capture and its Z-order walk. never attempted.

### windows-desktop

9 open of 11.

- [H-001](tasks/001-bring-up-and-streamed-turn.md) The bring-up: hotkey, tray, and a streamed turn. never attempted.
- [H-002](tasks/002-core-audio-volume-action.md) The real Core Audio volume action. never attempted.
- [H-003](tasks/003-real-reminder-toast.md) A real reminder toast. never attempted.
- [H-004](tasks/004-confirm-card-over-ipc.md) The confirm card through real Tauri IPC. never attempted.
- [H-005](tasks/005-session-read-commands.md) The session-read Tauri commands. never attempted.
- [H-006](tasks/006-preference-commands-across-restart.md) The preference Tauri commands across a restart. never attempted.
- [H-007](tasks/007-reminder-pull-surface.md) The reminder pull surface on the hotkey path. never attempted.
- [H-008](tasks/008-connection-indicator-ipc-hop.md) The connection indicator's real IPC hop. never attempted.
- [H-009](tasks/009-unbalanced-com-initialization.md) Unbalanced COM initialization on the blocking pool. ongoing: an observation to make over months of real use, never a check that passes.
- [H-010](tasks/010-pgdata-on-windows-drive.md) PGDATA directly on the Windows drive. never attempted.
- [H-011](tasks/011-toolchain-linked-full-build.md) The toolchain-linked full build. ongoing: an obligation on every change to these trees, not a check to run once.

<!-- backlog:end -->

## Which session first

Ordered by what unblocks the most, and grouped so each group is one session.

1. **The Windows desktop session.** One bring-up covers eight checks, the first of which is that
   bring-up. Start here because it is the cheapest and closes the most items at once, and because
   the confirm card and the toast are the two consent surfaces the safety position rests on.
2. **The capture session.** Its own bring-up. Do the self-exclusion check first inside it and not
   last: if it fails, the loop it prevents is already live and the rest of the session is pointless.
3. **The rest of the G list in one long session**, in the order the GPU tasks give, since they share
   one bring-up and one blocker. Three of them want the overlay up beside the brain, so if the
   desktop and the card are two machines, that session splits. The deep-model pick that used to head
   this list was **done 2026-08-04** by the agent; it is gemma-4-31B QAT q4_0 and its numbers are in
   [ADR-0004](../adr/ADR-0004-model-lineup.md). The injection-harness run and the GPU-placed subagent
   were done the same day.
4. **The overlay polish.** An authoring pass rather than a bring-up. It can fail review rather than
   fail a check, and it is the only thing here that is not urgent for correctness.
5. **The screen-reader pass.** Uses the same bring-up as the Windows desktop session and can be
   folded into it if NVDA is already installed; kept separate because it needs a reader and a speech
   viewer, and because it produces a transcript rather than a pass. Added 2026-08-07 when the
   overlay's live region learned to report a list that shrank.

The two ongoing items in the Windows desktop session never appear in this order: one is an
observation to make over months of real use, the other is a per-change obligation.

## Prerequisites, per capability

A session fails on setup more often than on anything else. Have these before starting.

**For W (any Windows item):**

- Rust (stable) and Node, with `npm ci` run in `body/app`; the Tauri CLI is a devDependency, so
  `npm run tauri …` needs no global install.
- The WebView2 runtime (preinstalled on Windows 11; otherwise the Evergreen runtime).
- A reachable brain at `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`).
- `CORTEX_SEAM_TOKEN` set **identically** for the brain stack and for the shell before `tauri dev`.
  A body without the token gets `Unauthenticated` on every call.
- For anything the **brain dials the body** for (volume, the toast):
  `CORTEX_BODY_ADDR=0.0.0.0:50151`, the brain brought up with `-f docker/docker-compose.body.yml`,
  and a Windows firewall allowance for that port. This crossing is the untested half of ROADMAP
  assumption 3.
- For the confirm card: a tool that needs approval. Either `CORTEX_EMAIL_SEND_ENABLED=true` with the
  Bridge reachable, or any tool name in `CORTEX_TOOLS_GATED`.
- Full runbook: [runbooks/body-overlay.md](../runbooks/body-overlay.md) section B.

**For G (any 24 GB item):**

- The models mount reachable by Docker and the GPU visible through the container toolkit
  (`just up-gpu`); see [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md). The mount's host
  directory is `CORTEX_MODELS_DIR` (default `./models`), which compose interpolates, so the calling
  shell or a repo-root `.env` sets it.
- **Escalation takes three brain settings together**: `CORTEX_ESCALATION=1`,
  `CORTEX_MODELHOST_BACKEND=supervisor`, and `CORTEX_BRAIN_ENDPOINT=http://model-host:8081`. Without
  the last one the brain refuses to boot and restarts forever on
  `CORTEX_BRAIN_ENDPOINT is required when CORTEX_ESCALATION=1` (`config_swap.py`).
  `docker/docker-compose.gpu.yml` sets that endpoint and `CORTEX_MODELHOST_ENDPOINT` itself and
  passes the other two through from the host by name, so a `.env` entry or an exported shell
  variable supplies them. Until 2026-09-17 nothing passed them, and both were silently ignored.
- `CORTEX_MODEL_FILE_BRAIN`, with `CORTEX_NGL_BRAIN` and `CORTEX_CTX_SIZE_BRAIN` to fit it, is
  model-host side and **is** interpolated, so `.env` or the calling shell supplies it. It is what
  puts the deep tier in the roster at all.
- **The deep tier does not start itself.** Naming its artifact puts it in the roster; at boot the
  sidecar starts the cortex and nothing else. Starting the deep model is two commands issued by
  hand, a stop of the cortex and a start of the deep tier against the model host's control API.
- Enough free VRAM that the brain tier can be the only resident model (13 to 18 GB by estimate).
- **For the three W+G items only: a Windows desktop too**, with the overlay running against this
  same brain. The W prerequisites above apply in full to that half.
- The whole sequence, with what it was observed doing on 2026-07-19, is
  [The GPU session, start to finish](#the-gpu-session-start-to-finish) below. Follow it there rather
  than assembling it from this list. Its last step is the teardown, with the two commands that
  **verify** the stack is gone: a model host left running holds the whole card.

## The GPU session, start to finish

The GPU items share one bring-up and one dependency chain, so both live here rather than being
restated in each task. Every output below was copied from a run on the dev machine on 2026-07-19
rather than reasoned about.

What remains on this side of the work, per item 7 of
[ADR-0030](../adr/ADR-0030-brain-handoff.md)'s "what is left" list: the brain pick, the tier-scale
swap, measured timings, the runbook, and the injection-harness run. That ADR says why the last of
those cannot move here: CI has no GPU and the older dev GPU could not hold the cortex beside a 31B
brain, so the swap's **mechanism** was validated by the agent against real `llama-server` processes
with two small stand-ins (started, health-checked, evicted, swapped, killed under the daemon, and
restarted over their own corpses) while **tier scale and its VRAM arithmetic** stay host-validated.
One correction to that list: **the runbook exists.**
[runbooks/model-swap.md](../runbooks/model-swap.md) was written on 2026-07-18 with the measured
mechanism in it. What is owed is the user filling in its tier-scale sections, one of which reads
"Record the timings here".

### The dependency chain

```
1. deep-model pick  ──┬──> 2. tier-scale swap ──┬──> 3. chaos kill at scale
                      │                         └──> 4. measured timings
                      └──> 5. the ~31B injection-harness run

6. GPU subagent beside the cortex · 7. cgroup caps                            (independent)
   (done 2026-08-04)
```

Items **2, 3 and 4 are W+G**: they need a real handoff, a handoff starts at an approved confirm
card, and the overlay is the only client that answers one. Items **1, 5, 6 and 7 are G**: the card
alone. If both capabilities live in one laptop the distinction costs nothing; if they do not, do 1,
5, 6 and 7 on the card and keep 2, 3 and 4 for a session with the desktop in the room. **1, 5 and 6
are done as of 2026-08-04**, all by the agent, and 7 is the only card-alone item left.

### The bring-up, start to finish

Derived from `docker/docker-compose.gpu.yml`, the `justfile`,
`brain/packages/model_manager/src/cortex_model_manager/api.py`, and
`brain/packages/orchestrator/src/cortex_orchestrator/config_swap.py`, then **run end to end on the
dev machine on 2026-07-19**, with every output below copied from that run.

**The deep tier does not start itself.** At boot the sidecar's daemon starts the cortex and nothing
else (`model_host_lifespan` in `api.py`), and no compose setting starts a second tier. The deep
model begins loading when you POST to the control API, and on a card that cannot hold both it begins
only after the cortex is stopped. Both are steps you issue by hand, and they are steps 4 and 5.

Steps 1 to 9 are the whole of **item 1**, which needs neither escalation nor the overlay: the pick
is measured by driving the sidecar directly. Step 10 and the overlay are what items 2, 3 and 4 add.
Item 5 runs on none of this: it starts its own container, so it wants the stack **down**.

1. **Name the models directory and the deep artifact.** All four are interpolated on `model-host`,
   so a repo-root `.env` or the calling shell supplies them:

   ```
   CORTEX_MODELS_DIR=<the host dir holding the GGUFs>
   CORTEX_MODEL_FILE_BRAIN=<the candidate's path under that dir>
   CORTEX_NGL_BRAIN=99
   CORTEX_CTX_SIZE_BRAIN=<the context the brain phase will use>
   ```

   A tier with no artifact file is not in the roster at all, so before a pick is named the deep
   model answers 404 and boot recovery logs one. That is a stock stack behaving as designed, and it
   is also the only way into the roster: nothing a request sends can name a model into existence
   (`api.py`).

2. **Bring it up** with `just up-gpu`, which is `docker compose --project-directory . -f
   docker/docker-compose.yml -f docker/docker-compose.gpu.yml up -d --build`. `depends_on` holds the
   brain until the sidecar reports a tier that can serve a turn as READY. Here, with both images
   already built and the cortex at `CORTEX_CTX_SIZE=4096`, that took 48.9 s and ended:

   ```
    Container cortex-model-host-1 Healthy
    Container cortex-brain-1 Starting
    Container cortex-brain-1 Started
   ```

   Every command below goes through the sidecar's control API, which is deliberately unpublished
   (it starts and stops processes on the container holding the GPU and the models mount), so each
   one is a `docker compose exec`. The prefix is long, so the rest of this section abbreviates it
   the way the derivation run did:

   ```
   GPU="--project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml"
   ```

3. **Ask the sidecar what it has.** This checks that the deep tier is in the roster at all, and it
   is worth doing before anything else, because a mistyped `CORTEX_MODEL_FILE_BRAIN` is silent: the
   tier simply is not there.

   ```
   docker compose $GPU exec model-host curl -s http://127.0.0.1:9300/health
   docker compose $GPU exec model-host curl -s http://127.0.0.1:9300/models/cortex
   docker compose $GPU exec model-host curl -s http://127.0.0.1:9300/models/brain
   ```

   ```
   {"status":"ok","models":["cortex","brain"],"stop_grace_s":10.0,"reap_timeout_s":30.0}
   {"model":"cortex","state":"ready","detail":"serving on port 8080"}
   {"model":"brain","state":"stopped","detail":"no process is running"}
   ```

   `"models":["cortex","brain"]` is step 1 having worked. `"state":"stopped"` on the deep tier is
   the point above: it is in the roster and it is not running, and nothing will start it for you.
   Since 2026-08-07 that health body also has `device_free_mib` and `device_total_mib`, the card as
   the sidecar's own `nvidia-smi` sees it, which is what a swap checks the deep tier's declared cost
   against. `nvidia-smi` read 7916 MiB of 8188 at this moment, which is the resident cortex.

4. **Stop the cortex**, which is what frees the card for the deep model. On 24 GB this is not
   optional either: the cortex costs 8.4 to 8.6 GiB measured (reserved at 8.6 since 2026-08-07, 11.3
   before that) and the candidates are 15 to 18 GB.

   ```
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/cortex/stop
   ```

   ```
   {"model":"cortex","state":"stopped","detail":"no process is running"}
   ```

   It answered in **0.53 s** with the child idle and VRAM fell to 551 MiB. A cortex with a request
   in flight costs the full `CORTEX_MODELHOST_STOP_GRACE_S` instead (10 s, measured in
   [runbooks/model-swap.md](../runbooks/model-swap.md)); the stop does not answer until the child is
   dead and reaped, which is why you wait for this reply before step 5.

5. **Start the deep tier.**

   ```
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/brain/start
   ```

   ```
   {"model":"brain","state":"loading","detail":"pid 279 is not serving yet"}
   ```

   It answered in **0.12 s**, because that is a spawn and not a load. The load is what you wait for
   next, and `loading` is the accurate answer until the child serves.

6. **Poll until it is ready.** Nothing pushes you a notification; the state changes under
   `GET /models/brain`:

   ```
   docker compose $GPU exec -T model-host curl -s http://127.0.0.1:9300/models/brain
   ```

   ```
   t=0s  {"model":"brain","state":"loading","detail":"pid 279 is not serving yet"}
   ...
   t=38s {"model":"brain","state":"ready","detail":"serving on port 8081"}
   ```

   Two things to expect at tier scale that this run was too small to show. A load of a 15 to 18 GB
   GGUF off the mount is minutes, not the 38 s above, and while it runs **neither tier serves**, so
   the `model-host` container turns unhealthy after about 150 s of it; that is a handoff in
   progress, not a fault, and [runbooks/model-swap.md](../runbooks/model-swap.md) says so under
   manual recovery. A child that dies instead reports `{"state":"failed", ...}` with its exit code
   in the detail, and its own reason is in `docker compose logs model-host`.

7. **Measure it, and ask it something.** This is item 1's actual content. `nvidia-smi` is the VRAM
   number; the tier's own OpenAI-compatible API on 8081 is the answer-quality half:

   ```
   docker compose $GPU exec model-host curl -s http://127.0.0.1:8081/v1/models
   docker compose $GPU exec model-host curl -s http://127.0.0.1:8081/v1/chat/completions \
     -H 'Content-Type: application/json' \
     -d '{"messages":[{"role":"user","content":"<your question>"}],"max_tokens":120}'
   ```

   `/v1/models` names the artifact path that is actually serving, which is how you know you measured
   the candidate you meant to. **Read the reply carefully before judging quality**: the gemma
   candidates are reasoning models, and in this run the whole 120-token budget went to
   `reasoning_content` with `"content":""` and `"finish_reason":"length"`. A candidate scored on that
   would look mute when it was thinking. Give it a budget that fits a chain of thought plus an
   answer, and read `reasoning_content` as well as `content`. The reply also has its own `timings`,
   which is the per-token speed without a stopwatch (this run: 120 tokens in 2072 ms).

8. **Swap back**, which is the same two verbs in the other order, and is worth doing by hand once
   before item 2 asks the brain to do it under a turn:

   ```
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/brain/stop
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/cortex/start
   ```

   The stop answered in 0.48 s and VRAM fell to 746 MiB; the cortex start answered in 0.10 s and the
   tier read `{"model":"cortex","state":"ready","detail":"serving on port 8080"}` **65 s** later,
   back at 7920 MiB. Note what the container health did through all of this: with the cortex stopped
   and the deep tier READY, `model-host` still read healthy, because its check asks for either tier,
   and `brain` read healthy throughout, because its check asks only that the `Health` RPC answered.

9. **Tear down, and verify the teardown with a command.** `just down-gpu` removes the stack
   including a locally layered override, since `down` works from the project's own labels:

   ```
   just down-gpu
   docker ps -a
   nvidia-smi --query-gpu=memory.used --format=csv,noheader
   ```

   Here that removed `cortex-brain-1`, `cortex-redis-1`, `cortex-model-host-1` and the
   `cortex_default` network, and VRAM fell to 610 MiB. **Run those last two lines rather than
   assuming.** A model host left running holds the whole card, and this repo has already spent a
   round on a cleanup that was claimed and not checked.

10. **Only for items 2, 3 and 4: turn escalation on from the host.** Add these two lines to the
    repo-root `.env`, or export them in the shell that runs `just up-gpu`:

    ```bash
    CORTEX_ESCALATION=1
    CORTEX_MODELHOST_BACKEND=supervisor
    ```

    The GPU override passes both into the brain by name and already sets `CORTEX_BRAIN_ENDPOINT` and
    `CORTEX_MODELHOST_ENDPOINT`, so do not add either. `config_swap.py` fails the brain at boot on
    escalation without a backend, and the container then restarts forever rather than serving.
    Before starting, `docker compose --project-directory . -f docker/docker-compose.yml -f
    docker/docker-compose.gpu.yml config brain` shows both under `brain:` with the values you set;
    `null` there means the variable did not reach compose.

11. Read [runbooks/model-swap.md](../runbooks/model-swap.md) before item 2, whose opening paragraph
    states which of its numbers are the mechanism's and which are a tier's. When a live test needs
    the control API from the host rather than through `exec`, `just up-modelhost-loopback` layers
    `docker/docker-compose.modelhost-loopback.yml` (control API on 9300, deep tier on 9081), and
    `just down-gpu` takes it down again.

**What the dev machine could and could not reach (2026-07-19).** Every step above ran on the 8 GB
card with the models on `/srv/models`, so the sequence is observed rather than inferred. **The one
step this card could not prove is the artifact in step 1.** A real candidate is 14 to 17 GB and this
card has 8188 MiB, so the run above pointed the deep tier at
`google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf` (4.9 GB) as a stand-in. It proves the
roster, the eviction, the start, the health check, the tier's own API and the swap back, and it
proves **none** of the arithmetic: the 38 s load, the 3801 MiB and the token rate are the stand-in's.
Everything else holds: the cortex tier served at `CORTEX_CTX_SIZE=4096` (the shipped 16K cortex is
ADR-0004's 11.3 GB), a brain with all three escalation settings booted healthy, and the two live
streaming tests in `brain/packages/inference/tests/test_backend_live.py` passed against it through
the real `LlamaCppBackend`. Dropping `CORTEX_BRAIN_ENDPOINT` was confirmed to be a restart loop, and
putting the three settings in the shell instead of the compose file was confirmed to leave the
container with none of them, which the pass-through of 2026-09-17 changed. One thing to expect on
the host box too: the rest of the `just brain-inference-live` suite starts its own `llama-server` on
`127.0.0.1:8080`, which the sidecar already publishes, so those tests fail on the port rather than
on the stack.

Where the dev machine stops is the tier itself, and not in the way the design predicted. Pointed at
`gemma-4-31B-it-qat-q4_0` (a 17 GB artifact) with the cortex evicted first, the deep tier did
**not** fail: llama.cpp logged `failed to fit params to free device memory: n_gpu_layers already set
by user to 99, abort`, kept every layer on the GPU anyway, reported READY after 373 s with
`nvidia-smi` steady at about 7.7 of 8188 MiB, and then generated 16 tokens in 36 s, which is roughly
half a token per second and is what a WSL2 driver spilling into host RAM looks like. So a card that
cannot hold the tier gives a green swap and numbers that mean nothing, which is the trap this
session exists to avoid. Two consequences worth taking in: no timing, VRAM figure, or answer quality
from an undersized card is a tier-scale result, and that 373 s load already exceeds the shipped
`CORTEX_SWAP_LOAD_TIMEOUT_S` default of 300 s, which is item 4's question.

**Both of those are settled on the real card as of 2026-08-04**, and the trap is worth rereading
against the answer: the same `gemma-4-31B-it-qat-q4_0` artifact that took 373 s and generated half a
token per second on 8 GB loads in 99.6 s and generates at about 31 tok/s on a card that holds it,
resident at 19128 MiB. The 373 s figure was the spill, not the model.

### Withdrawn from this session: the resident VRAM figure with the projector loaded

This doc shipped on 2026-07-19 with an eighth item asking for the resident cortex plus `mmproj`
footprint on the 24 GB card at production context. **It was withdrawn the same day, because the repo
already had that measurement**, in three places: the 2026-06-29 cortex reading in
[model lineup](../readings/model-lineup.md), whose row for `gemma-4-12B q4_0` reads `11.0 GB`
weights only and `11.3 GB (mmproj 0.18 GB, +0.3)` with vision, measured on the 24 GB card at 16K
context, single slot, all layers on GPU, which is the deployment's own slot count
(`model_manager/config.py` gives the cortex tier `parallel=1`); the
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) table, whose header says the numbers are
`nvidia-smi` total used with the model resident; and
[runbooks/vision.md](../runbooks/vision.md)'s "What the projector costs", which states that
ADR-0004's 11.3 GB cortex reservation is a with-mmproj measurement. ADR-0029 decision 14 says the
same. It is recorded here rather than deleted silently, since a reader following an older pointer to
"item 8" deserves to find out why it is gone.

### The reopen branch, and what else this hardware makes testable

Design work recorded in [refinements/](../refinements/index.md) that becomes *testable* here for the
first time: the NPU feasibility pass, which stays in that backlog with its code cost. See "Not host
work, but unblocked by this hardware" below. Co-residency was on that list and was settled
2026-08-07 by the agent in Docker rather than in a host session.

One more joined on 2026-08-09, from the change that made a peer tier's failed restart a record the
placer and the body/brain boundary read (ADR-0054 decision 3): **the reopen branch, where a retry
pass observes a real tier `ready` again and GPU placement resumes.** Its failure side was witnessed
against the real sidecar over real HTTP that day, including a tier the daemon refuses outright and
one that accepts a start and dies; what needs a loadable GGUF, and so needs the model drive mounted,
is a tier that genuinely comes back. It is one `docker run` of `model-host` with a real artifact
named and a few lines driving `sweep_tiers`, so it belongs to whichever session next has the mount.
The pass it drives got wider on 2026-08-11 and the observation did not: a pass reads every evictable
tier rather than only the marked ones, so what is still unwitnessed is the same single branch, a
tier that was down and is now serving.

Three more used to be listed here, on the premise that no card the agent has can run the cortex: the
spontaneous-pick nudge's live uptake and the model passes behind session-history summarization and
the reranker. Corrected 2026-07-19, since the dev GPU does run the cortex at 4K. What this hardware
still adds to them is the production 16K context and more than one slot, which is a sharper judgment
rather than the only possible one.

## Decisions awaiting the user

Weighed, not run. Each stays at its ADR, which is the correct home for a decision; these are
pointers so they are not lost.

- **Five risks flagged for maintainer review** in
  [ADR-0030](../adr/ADR-0030-brain-handoff.md#risks-flagged-for-maintainer-review): the default that
  escalation needs approval (a config plus one check to reverse), the model-host sidecar design
  versus a docker-socket controller, the unmeasured brain-tier swap latency, two assistant messages
  under one turn id, and whether the brain phase should have the cortex's full dispatcher.
- **Whether a tainted turn may escalate, now that the deep tier is measured.** The first of those
  five risks was waiting on a number and has one as of 2026-08-04: the brain pick obeys 0 of 10
  framed injections. That retires one of the two reasons the hard deny rests on and leaves the
  other, that injected content must not force an eviction, untouched, so the agent published the
  number and changed nothing. Two corrections to the risk's own wording are worth reading with it,
  both stated in [ADR-0030](../adr/ADR-0030-brain-handoff.md): the deny is the generic approval
  branch shared by every tool that needs approval rather than an escalation setting, and the
  recorded alternative keeps a taint refusal rather than removing one.
- **Whether screen capture should ship behind an approval.**
  [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) risk 2: capture needs no approval, so an
  injected tool result can drive a capture in the turn it arrived in. The ADR says plainly that the
  user may reasonably overrule it, and names the paragraph to weigh when doing so.
- **The confusables fold table.** [ADR-0015](../adr/ADR-0015-output-guardrail.md) calls it
  "user-reviewable; the table is one edit to trim".
- **The completion chime.** The last open line of
  [design/overlay-ux.md](../design/overlay-ux.md) section 9; the rest of that section was settled by
  the 2026-07-03 and 2026-07-12 user passes, and the corner default is folded into the overlay
  polish task.

## Not host work, but unblocked by this hardware

These are recorded in [refinements/](../refinements/index.md) and stay there, because each is a
design decision with a code cost. They are listed here only so a session on the host's hardware
records what it could also settle:

- **The Intel NPU as a third placement target** (`resource-governance`): a feasibility pass, whose
  likely blocker is reachability from the dockerized WSL2 brain.
- **The spontaneous-pick nudge's live uptake** (`subagents`): whether a live cortex reaches for
  distinct roster models unprompted, over real use rather than one scripted ask. **The scripted half
  ran 2026-08-04**, at the production 16K context with a single slot rather than the 4K its entry
  proposed, so the old claim that this hardware buys "real use at production context" is narrower
  than it was: the context was not what was missing. A prose-only ask never delegated at all; an
  invited one delegated in all 16 turns and piled the whole batch on one entry in all 16. What is
  left for this hardware is the same question over months of real use rather than over 36 scripted
  turns.
- **Session-history summarization and the model-based reranker** (`session-history`, `memory`): both
  were listed here as needing `select` to go async first, with summarization's cache-versus-recompute
  question undecided. **Both blockers are gone as of 2026-08-06 and both passes shipped**, so that
  sentence is false about the tree and is kept only as the record of what was believed. Both `select`
  methods are `async`, the recall one widened once for the reranker, and the declined
  blended-relevance field and the recall trail are in
  [ADR-0038](../adr/ADR-0038-ranked-recall.md). What is left is the half that was always the
  accurate one: both were measured on the agent's own runs, on one hand-built corpus each, so what
  this hardware still buys is the same judgment over real conversations. The judge's default **was
  decided 2026-08-08**: the user asked for the turn cost before the change, the change followed the
  number (a recalling turn's time to first token rises 0.515 s, against a raw-versus-raw control
  whose interval spans zero), and `CORTEX_MEMORY_RECALL` ships as `judge`.
- **Unbalanced COM initialization on the blocking pool** (`body-gateway`): the fix is code and stays
  there; the *observation* that would trigger it is an ongoing watch item in the Windows desktop
  session.
- **Co-residency** (`inference-model-manager`) was on this list and **was settled 2026-08-07 by the
  agent, in Docker against the real tiers**, so it was never host work in the end:
  `CORTEX_SWAP_CORESIDENT` ships off by default, the cortex and the deep model measured as not
  co-fitting (and, under WSL2, as silently paging rather than failing), and the deep model and the
  shipped subagent tier measured as fitting with 908 MiB to spare.

**The caveat on those entries, resolved rather than left open (2026-07-19).** Each gave "the cortex
tier does not fit the 8 GB dev GPU" as part of its reason, and that clause is false:
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md) measured the cortex resident on the dev GPU
beside its projector at 4K on 2026-07-17 and drove a real turn through it the next day, and
[ADR-0030](../adr/ADR-0030-brain-handoff.md) records what that leaves, the model alone taking 7715
of the card's 8188 MiB. Settled per entry: the nudge probe is agent-runnable, and the two model
passes were never hardware-blocked at all. What genuinely wants this hardware is the same judgment
at 16K with more than one slot, so they stay listed above as things a session here could also
settle.
