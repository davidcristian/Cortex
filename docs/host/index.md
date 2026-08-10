# Host-side work: index

Every piece of work only the maintainer can perform, one self-contained doc per sitting, extracted
from the ROADMAP's slice statuses on 2026-07-19 with the load-bearing wording kept verbatim. This
is the companion to [refinements/](../refinements/index.md) and the two hold different things:

- **[refinements/](../refinements/index.md) holds deferred *design*.** Work anyone can pick up once
  a seam, a consumer, or a decision unblocks it. Its entries describe code that is not written.
- **This directory holds work that is blocked on hardware the dev machine does not have.** The code is
  written; what is missing is a machine that can run it. Almost every item here is a *validation*,
  and the one that is not, the overlay polish pass, says so at the top of its section.

Neither is "host-only" in the [AGENTS.md](../../AGENTS.md) sense. An `integration`-marked live test
is host-only because it needs Docker, a GPU, or a network service, and gate 3 is explicit that "on
the host" **includes the agent**: those run here, in this repo, by whoever is working. An item
lands in this directory only when the agent's dev machine physically cannot do it.

## The two capabilities

Every item below carries one of these two tags or both of them, and mixing them wastes a sitting:

| Tag | What it means | Why the dev machine cannot stand in |
| --- | --- | --- |
| **W** | A real Win32 desktop session, where the body runs natively | The dev machine is Linux under WSL2. Nothing OS native (COM, WinRT, GDI, a real Tauri IPC hop, a real window) exists to exercise. |
| **G** | A card that holds the real model tiers (24 GB) | **Nothing, since 2026-08-04.** See the correction below: the development card holds the tiers, so a G item is agent-runnable. |

**The G premise was false, and the correction is worth more than the tag.** This table shipped
saying the dev GPU is an 8 GB card, so that no tier pair, no ~31B model and no GPU-placed subagent
beside a resident cortex was reachable. [ADR-0030](../adr/ADR-0030-brain-handoff.md) did measure
`gemma-4-12b-it-qat-q4_0.gguf` alone taking 7715 of that card's 8188 MiB, and every figure derived
from that card stays true of it. The premise that failed is the one underneath: that the 8 GB card
is the card the repo is developed on. On 2026-08-04 the development machine reported 24463 MiB and
ran the deep-model pick end to end, loading and serving all four candidates alone on the card, and
[gpu-tier-scale.md](gpu-tier-scale.md) item 1 records the result. **So G on its own is no longer a
reason to file work here.** [AGENTS.md](../../AGENTS.md) is explicit that "on the host" includes
the agent and that GPU and model behavior reachable through Docker is done now rather than
deferred, and that is the rule this table was quietly contradicting.

Two things this does **not** change. **W is untouched**, and it is now the only tag doing real
work here: a Win32 desktop session is still something no agent can stand in for. And **the three
W+G items are still blocked**, on their W half alone, for the reason the next paragraph gives.
The plain G items that remain are listed because each is its own sitting with its own bring-up,
not because the VRAM is missing.

**W+G exists, and it is exactly three items: 2, 3 and 4 of
[gpu-tier-scale.md](gpu-tier-scale.md)** (the tier-scale swap, the chaos kill during one, and the
timings of one). A handoff begins only when the confirm card gating `escalate_to_brain` is
approved, that card is a `ConfirmRequest` on the Converse stream, and the only shipped client that
answers one is the overlay; the arithmetic those items exist to prove needs the 24 GB card. Both
capabilities, or the sitting stalls at the card. Marked 2026-07-19 after an audit tried to execute
them from the GPU doc alone.

**The tag was withdrawn earlier the same day, from two items that did not need it**, and the
correction is worth keeping because it is the same mistake in the other direction. This table
shipped claiming that a fully cortex-driven `set_volume` and the end-to-end answer on the capture
path each need both capabilities at once. That rested on an older sentence saying the 12B cortex
does not fit 8 GB, which [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) had already measured
false on 2026-07-17: at `--ctx-size 4096 --parallel 1` the cortex fits the dev GPU **beside its
projector**, which is the harder of the two cases, and it drove a real vision turn there on
2026-07-18. Both items are therefore **W**. The tag matters in both directions: a W+G item is one
the user must not start until both capabilities are in the room, and if the Windows host and the
24 GB card turn out to be two machines, a wrong tag costs exactly the trip the tagging exists to
prevent.

**Tagged by capability, not by machine name, deliberately.** The repo's own evidence says the
Windows host and the 24 GB card are one laptop: [ARCHITECTURE.md](../ARCHITECTURE.md) says "Three
tiers share one 24 GB GPU" and [ADR-0004](../adr/ADR-0004-model-lineup.md) says
"First real bring-up on the 24 GB card". But
**no document states it**, so the layout does not assume it. A capability tag is correct whether
that is one desk or two, and if it turns out to be two, only the tags need rereading and not the
directory. Settling this in writing is worth one sentence in an ADR the next time one is opened.

## The docs

| Doc | Tag | What one bring-up buys | Open |
| --- | --- | --- | --- |
| [windows-desktop.md](windows-desktop.md) | W | One `npm run tauri dev` beside a running brain: the hotkey and one streamed turn, volume, the toast, the confirm card, the session commands, the preference commands and the appearance surviving a restart, the reminder surface, the connection dot | 8 checks + 1 optional + 2 standing |
| [windows-capture.md](windows-capture.md) | W | The screen-capture path, which needs its own switch, its own receipts, and its own expectations. Carries the single highest-consequence check in the repo, since 2026-08-08 the two failure sentences only a real GDI backend can produce, and since 2026-08-10 the Z-order walk behind a targeted capture, which brings a second check of the same kind (the walk must never land on the overlay) | 2 checks, 12 observations |
| [overlay-polish.md](overlay-polish.md) | W | The one item here that is **authoring, not validation**: the OS-window half of the overlay | 1 build (4 parts) + 1 design decision |
| [overlay-screen-reader.md](overlay-screen-reader.md) | W | A reader pointed at the running overlay: what the live region is actually *spoken* as, which is the half no accessibility tree holds | 1 observation session (8 gestures) |
| [gpu-tier-scale.md](gpu-tier-scale.md) | G, and W+G for three | The 24 GB machine: everything the deep-model pick unblocks, plus the measurements the placer and the caps ship without. Items 2, 3 and 4 need the overlay to trigger the handoff | 4 open; the pick, the injection run and the GPU-placed subagent all done 2026-08-04 |

User **decisions** (weigh, do not run) stay at their ADRs and are listed at the bottom of this
page rather than copied, so a decision has exactly one home.

## Why the split is by sitting

Three splits were considered and rejected before this one:

- **By machine.** Rejected for the reason above: no document says there are two, and the layout
  would encode an unverified premise where it is expensive to correct rather than in a tag where
  it is cheap. The correction above is the argument's own evidence: two items changed tag on the
  day the directory landed, and only a table cell moved.
- **By slice.** Slices are a historical ordering and the ROADMAP is the thing being cleaned. User
  work accumulates per surface, not per slice: six different slices all end in "press the hotkey
  and look at the overlay". A slice split hands the user six docs for one sitting.
- **By refinements area, mirroring the precedent exactly.** Seventeen area docs produce host work
  in six, and three of those (body gateway, scheduling, vision) collapse to the same physical act.
  Fragmenting for symmetry costs context, and context bloat is a defect.

What is left is the boundary that actually matters to the person doing the work: **what one
bring-up buys**. Capture and the polish pass get their own docs despite being W, because each has
a different bring-up and a different failure mode, and the capture check is one that gets skipped
if it is the sixth bullet on a tired evening.

## A host item's expected outcome is a hypothesis

The refinements index carries a standing warning that an entry's own *cost* estimate is a
hypothesis. The analogue here is different: a host item's own *predicted result* is a hypothesis,
and this repo has been wrong about one more than once.
[ADR-0012](../adr/ADR-0012-resource-governance.md) predicted a CUDA OOM path that the shipped
re-place deliberately did not build; [ADR-0023](../adr/ADR-0023-body-gateway-volume.md) recorded
`CaptureScreen` as "behind the same seam" and it cost five proto fields plus a port method. So the
"Pass looks like" lines below are what the design expects, not what will happen. When a run
contradicts one, the run wins and the ADR gets a dated addendum saying so. That correction is the
most valuable thing a user sitting produces.

## Prerequisites, per capability

Sittings die on setup. Have these before starting.

**For W (any Windows item):**

- Rust (stable) and Node, with `npm ci` run in `body/app`; the Tauri CLI is a devDependency, so
  `npm run tauri …` needs no global install.
- The WebView2 runtime (preinstalled on Windows 11; otherwise the Evergreen runtime).
- A reachable brain at `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`).
- `CORTEX_SEAM_TOKEN` set **identically** for the brain stack and for the shell before
  `tauri dev`. An untokened body gets `Unauthenticated` on every call.
- For anything the **brain dials the body** for (volume, the toast): `CORTEX_BODY_ADDR=0.0.0.0:50151`,
  the brain brought up with `-f docker/docker-compose.body.yml`, and a Windows firewall allowance
  for that port. This crossing is the untested half of ROADMAP assumption 3.
- For the confirm card: a gated tool. Either `CORTEX_EMAIL_SEND_ENABLED=true` with the Bridge
  reachable (the user's `netsh` portproxy), or any tool name in `CORTEX_TOOLS_GATED`.
- Full runbook: [runbooks/body-overlay.md](../runbooks/body-overlay.md) section B.

**For G (any 24 GB item):**

- The models mount reachable by Docker and the GPU visible through the container toolkit
  (`just up-gpu`); see [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md). The mount's host
  directory is `CORTEX_MODELS_DIR` (default `./models`), which compose interpolates,
  so the calling shell or a repo-root `.env` sets it.
- **The three escalation settings are brain-side and no compose file interpolates them**, so a
  `.env` entry or an exported shell variable is silently ignored and the stack comes up with
  escalation off. They go in the `brain` service's `environment:` block in
  `docker/docker-compose.gpu.yml`, which is what that file's own header instructs, or in a local
  override layered after it. They are needed together:
  `CORTEX_ESCALATION=1`, `CORTEX_MODELHOST_BACKEND=supervisor`, and
  `CORTEX_BRAIN_ENDPOINT=http://model-host:8081`. The last one used to be missing from this list:
  without it the brain refuses to boot and restarts forever on
  `CORTEX_BRAIN_ENDPOINT is required when CORTEX_ESCALATION=1` (`config_swap.py`).
  `CORTEX_MODELHOST_ENDPOINT` is already set by the GPU override, so do not add it.
- `CORTEX_MODEL_FILE_BRAIN`, with `CORTEX_NGL_BRAIN` and `CORTEX_CTX_SIZE_BRAIN` to fit it, is
  model-host side and **is** interpolated, so `.env` or the calling shell carries it. It is what
  puts the deep tier in the roster at all. Until the first item in
  [gpu-tier-scale.md](gpu-tier-scale.md) produces a pick, the tier answers 404 and boot recovery
  logs one, which is a stock stack behaving correctly rather than a fault. That item blocks four
  of the others.
- **The deep tier does not start itself.** Naming its artifact puts it in the roster; at boot the
  sidecar starts the cortex and nothing else. Starting the deep model is two commands you issue by
  hand, a stop of the cortex and a start of the deep tier against the model host's control API,
  and they are steps 4 and 5 of that doc's bring-up.
- Enough free VRAM that the brain tier can be the only resident model (13 to 18 GB by estimate).
- **For items 2, 3 and 4 only: a Windows desktop too, with the overlay running against this same
  brain.** Those three ride a real handoff; a handoff starts with the confirm card that gates
  `escalate_to_brain`, and the overlay is the only client that answers one. Bring both up, or take
  the card-alone items and keep the other three for a sitting that has both; of those, 1, 5 and 6
  were taken on 2026-08-04 and only 7 is left. The W prerequisites above apply in full to that half.
- The whole sequence, with what it was observed doing on 2026-07-19, is the "Before you start"
  section of [gpu-tier-scale.md](gpu-tier-scale.md). Follow it there rather than assembling it
  from this list. Its last step is the teardown, with the two commands that **verify** the stack is
  gone: a model host left running holds the whole card.

## Recommended order

Ordered by what unblocks the most, and grouped so each group is one sitting.

1. **The Windows desktop sitting** ([windows-desktop.md](windows-desktop.md)). One bring-up covers
   eight checks, the first of which is that bring-up. Start here because it is the cheapest and
   closes the most items at once, and because the confirm card and the toast are the two consent
   surfaces the safety posture rests on.
2. **The capture sitting** ([windows-capture.md](windows-capture.md)). Its own bring-up. Do the
   self-exclusion check first inside it and not last: if it fails, the loop it prevents is already
   live and the rest of the sitting is moot.
3. ~~**The deep-model pick**~~ ([gpu-tier-scale.md](gpu-tier-scale.md)). **Done 2026-08-04**, by
   the agent, once the G premise above was found false. It gated the swap, the chaos kill, the
   timings and the injection-harness run, and all four are unblocked; what still holds items 2, 3
   and 4 is the overlay. The pick is gemma-4-31B QAT q4_0 and its numbers are in
   [ADR-0004](../adr/ADR-0004-model-lineup.md).
4. **The rest of the G list in one long sitting**, in the order that doc gives, since they share
   one bring-up and one blocker. Items 2, 3 and 4 of it want the overlay up beside the brain, so
   if the desktop and the card are two machines, that sitting splits: 7 on the card, and
   2, 3 and 4 wherever both are. Item 5 was the third of the card-alone items and it is **done as
   of 2026-08-04**; it never shared this bring-up anyway, since it starts its own container and
   wants the stack down. **Item 6 is done the same day** and left 7 alone on the card side.
5. **The overlay polish** ([overlay-polish.md](overlay-polish.md)). A work session, not a sitting.
   It is authoring, it can fail review rather than fail a check, and it is the only thing here that
   is not urgent for correctness.
6. **The screen-reader session** ([overlay-screen-reader.md](overlay-screen-reader.md)). Rides the
   same bring-up as the Windows desktop sitting and can be folded into it if NVDA is already
   installed; kept separate because it needs a reader and a speech viewer, and because it produces a
   transcript rather than a pass. Added 2026-08-07 when the overlay's live region learned to report a
   list that shrank and the tree stopped being able to answer the last question about it.

The two standing items in [windows-desktop.md](windows-desktop.md) never appear in this order:
one is an observation to make over months of real use, the other is a per-change obligation.

## Every item, one line each

The order above groups sittings; this is the roll call. [AGENTS.md](../../AGENTS.md) requires a
host item to be recorded in three places, its sitting doc, its line here, and its origin decision
record, and a grouped order is not a line per item: added 2026-07-19 after the optional PGDATA
check was found sitting on two of the three. It was added naming a second example too, the
resident VRAM figure with the projector loaded, which turned out to be no host item at all;
that half of its founding evidence is withdrawn below. Statuses are not
repeated below, with the one exception the rule always anticipated: every item still reads
**never attempted** except the deep-model pick, the injection-harness run and the GPU-placed
subagent, all three done on 2026-08-04 and each carrying its status on its line, and each item's
own section stays authoritative.

**The rule has to hold in both directions, and did not until 2026-07-19.** It held forward, from
every item here to its line and its ADR, and failed backward: [ADR-0011](../adr/ADR-0011-body-v1.md)
named six Host-Windows lines and two of them, the hotkey and tray registration and the live
`converse` stream to the webview, had no item in this directory at all. Both are now check 0 of
[windows-desktop.md](windows-desktop.md), listed below. Reading an origin ADR's user list against
this roll call is the cheap way to catch that, and it is worth doing whenever an ADR gains a
host line.

**W, and these seven share one bring-up** ([windows-desktop.md](windows-desktop.md)):

0. **The bring-up itself: the hotkey, the tray, show and hide, and one streamed turn.** Numbered 0
   because everything below rides on it, so it is done first by construction. Closes two ADR-0011
   user lines that had no home until 2026-07-19.
1. **The real Core Audio volume action.** Blocked on nothing but the sitting, and it closes the
   fully cortex-driven `set_volume` with it.
2. **A real reminder toast.** Needs a fired reminder, so seed one before starting.
3. **The confirm card through real Tauri IPC.** Needs a gated tool armed, per the prerequisites.
4. **The session-read Tauri commands.** Needs a brain with prior chats in its store.
5. **The reminder pull surface on the live hotkey path.** Pairs with item 2 and the same seed.
6. **The connection indicator's real IPC hop.** Costs one brain stop and restart.

**W, each with its own bring-up:**

- **The whole GDI capture path** ([windows-capture.md](windows-capture.md)): one check with seven
  observations, its own kill switch, and the self-exclusion observation to be made first rather
  than last.
- **The OS-window half of the overlay polish** ([overlay-polish.md](overlay-polish.md)): the one
  **authoring** item here. Blocked on nothing; it is reviewed rather than passed.
- **What the live region is spoken as** ([overlay-screen-reader.md](overlay-screen-reader.md)):
  eight gestures read back through NVDA's speech viewer. Everything about those announcements that a
  machine can check is gated and measured (every region on the page, its computed `live`, `atomic`
  and `relevant`, the exact text before and after each gesture, and one mutation per gesture); what
  no tree holds is whether a reader voices it and what it does when a polite update and a focus
  change land in the same commit, which is what deleting the open chat does.
- **PGDATA directly on the Windows drive** ([windows-desktop.md](windows-desktop.md), optional and
  explicitly a nice to have): Docker on the Windows host, no Tauri app and no overlay. Nothing
  depends on the answer, and no procedure exists yet, so writing one is part of taking it.

**W, standing rather than a check** ([windows-desktop.md](windows-desktop.md)), which is why
neither appears in the recommended order:

- **Unbalanced COM initialization on the blocking pool:** an observation over months of real use.
  The fix stays in [refinements/body-gateway.md](../refinements/body-gateway.md) with its code cost.
- **The toolchain-linked full build:** a per-change obligation for anything touching
  `body/crates/os_windows` or `body/app/src-tauri`, not a one-time check.

**G, one bring-up and one blocker** ([gpu-tier-scale.md](gpu-tier-scale.md)), and **three of these
are W+G**, marked on each line:

1. **The deep-model pick. Done 2026-08-04**, the first item to leave this directory. **G**, and
   the run that proved G is no longer a reason to be here. Driven straight at the model host's
   control API with neither escalation nor the overlay, once per candidate. The pick is
   **gemma-4-31B QAT q4_0**, at 19128 MiB alone on the card and 99.6 s from start to READY; the
   result lives in [ADR-0004](../adr/ADR-0004-model-lineup.md)'s brain-pick addendum and the Brain
   rows of [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md). It unblocks 2, 3, 4 and 5.
2. **The tier-scale cortex to brain swap.** **W+G.** Blocked on the pick, and on having an overlay
   to approve the confirm card that starts a handoff.
3. **The chaos kill at tier scale.** **W+G.** Blocked on the pick and the swap. A failure here is a
   finding against the one hard rule.
4. **Measured swap timings.** **W+G**, inherited: these are the phases of the swap in item 2.
5. **The ~31B injection-harness run. Done 2026-08-04**, the second item to leave this directory and
   the first whose outcome could have changed shipped policy. **G**, a pytest that starts its own
   `llama-server` container, run with the model host down. The pick obeyed **0 of 10** framed
   injections against an unframed control that obeyed 1, so the deep tier is as robust as the
   cortex; the result lives in the [ADR-0013](../adr/ADR-0013-untrusted-content.md) addendum, the
   [ADR-0004](../adr/ADR-0004-model-lineup.md) injection table and a note at
   [ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 1, and the runbook section it owed is in
   [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md). Policy did not move: the run retires one
   of the two reasons the tainted-escalation deny rests on, and the choice is now a decision
   awaiting the user, listed below.
6. **A GPU-placed subagent beside a resident cortex. Done 2026-08-04**, the third item to leave this
   directory and the one whose split turned out not to matter. **G.** Independent of the pick.
   Narrowed 2026-07-19: the placer's GPU arm firing against a real placement at all needs no
   resident cortex and went back to the agent's list, leaving the fit test against a real 12B
   reservation here. Running the first with the cortex up **is** the second, so both closed
   together: the tiers cost 14.00 GB of `nvidia-smi` total used against a 14 GB soft cap and leave
   11110 MiB of the card free, while the shipped placeholders claim 16.8 GB for them, so the
   arithmetic and not the card is why no spawn had ever been GPU-placed. The numbers live in the
   [ADR-0012](../adr/ADR-0012-resource-governance.md) fit addendum and the measured table of
   [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md). **The "16.8 GB" is the record of what
   the placeholders claimed that day and stopped being true afterwards:** the reservation was
   re-measured to 8.6 GiB on 2026-08-07 and the ask to 3.5 GiB on 2026-08-08, so the pair now claims
   12.1 GB, sits inside the same 14 GB cap, and the shipped stack GPU-places a spawn. That is this
   item's own finding carried out rather than a correction of it.
7. **The cgroup cap numbers.** **G.** Independent, but best done under item 2's load, which is the
   only realistic one, so in practice it happens in the sitting that has both capabilities.

**Withdrawn 2026-07-19, the day it was filed: "the resident VRAM figure with the projector loaded,
at 16K".** It was filed as an eighth G item on the premise that it "existed in exactly one
sentence in this repo", a clause in
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md)'s Consequences. That premise was false. The
measurement exists: [ADR-0004](../adr/ADR-0004-model-lineup.md)'s 2026-06-29 addendum recorded
11.3 GB with the mmproj loaded, on the 24 GB card, at 16K context and a single slot, which
is the deployment's own tier shape (`config.py` gives the cortex `parallel=1`), and
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)'s table and
[runbooks/vision.md](../runbooks/vision.md)'s "What the projector costs" both carry it. ADR-0029
decision 14 says so itself: "The 11.3 GB default is ADR-0004's **with-mmproj** measurement". Asking
the user to re-measure it was manufactured work, which is worse than an omission, because an
omission does not cost a sitting.
**Half of that reasoning did not survive 2026-08-07**, and it is corrected here rather than left
standing. The measurement did exist and the withdrawal was still right, because this is not host
work: the agent reaches the GPU through Docker and measured it in one sitting. What was wrong is
the confidence that an existing figure settles the question. The 11.3 GB was `nvidia-smi` total
used with the desktop's own floor inside it, taken on a different llama.cpp build, and it was an
idle reading where the reservation it fed has to cover a peak. Re-measured at the shipped tier
shape the cortex is 8400 to 8484 MiB idle and 8573 MiB at its peak above a bracketed floor, and
`CORTEX_VRAM_CORTEX_GB` is 8.6 rather than 11.3
([ADR-0012](../adr/ADR-0012-resource-governance.md)'s re-measured-reservation addendum). So the
sentence to keep is that this was never the user's to do, not that there was nothing to find.

## Status convention

This is the one place this directory must **not** copy the refinements precedent. A refinement
lands or is declined; a user check can be attempted, inconclusive, and worth retrying. Each item
carries a status line, one of:

- **Never attempted.** The default, and what every item here but one says today.
- **Attempted YYYY-MM-DD, inconclusive:** with what happened. This is a real and useful state; an
  environment problem is not a failed check.
- **Done YYYY-MM-DD.** With the result written where the item's "Record it" line says. The
  deep-model pick is the first, on 2026-08-04, the injection-harness run the second and the
  GPU-placed subagent the third, all the same day.

## The exit contract

An item that completes writes its result back to its **origin ADR as a dated addendum** and into
its **runbook**, then leaves this directory. Same shape as a landed refinement, one difference:
refinements keep landed entries in place as the historical record of what a deferral became,
because their text often corrects its own ADR. A user check produces a *measurement*, whose home
is the ADR and the runbook, so this directory shrinks toward empty rather than accumulating.

**The first exit showed the contract needs one qualifier, added 2026-08-04.** The deep-model
pick's measurement did leave, to the model-lineup ADR and the GPU runbook, and its section in
[gpu-tier-scale.md](gpu-tier-scale.md) is now a heading, a status and a pointer rather than a
procedure. What could not leave is the heading itself: four items in that doc are written against
"item 1", so deleting the section would have cost a renumbering of every reference to buy back
twenty lines. **A completed item leaves its content, and keeps its number for as long as something
still depends on it.** Nothing changes for an item nothing points at; those go entirely.

The second exit, the injection-harness run later the same day, followed that qualifier without
needing it argued again, and added one of its own: **an item that owes a procedure exits by writing
the procedure, not by describing it.** That item's four warnings about how the harness fails were
its most reusable content, and leaving them in a completed section would have hidden them from the
next person to re-run the row, so they left for
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) with the measurement.

Emptiness here is load-bearing: the ROADMAP's finish line requires every slice, this
directory, and the refinements backlog all being clear.

## Decisions awaiting the user

Weighed, not run. Each stays at its ADR, which is the correct home for a decision; these are
pointers so they are not lost when the ROADMAP slims.

- **Five risks flagged for maintainer review** in
  [ADR-0030](../adr/ADR-0030-brain-handoff.md#risks-flagged-for-user-review): the gated-escalation
  default (a config plus one check to reverse), the model-host sidecar shape versus a docker-socket
  controller, the unmeasured brain-tier swap latency, two assistant messages under one turn id,
  and whether the brain phase should carry the cortex's full dispatcher.
- **Whether a tainted turn may escalate, now that the deep tier is measured.** The first of those
  five risks was waiting on a number and has one as of 2026-08-04: the brain pick obeys 0 of 10
  framed injections. That retires one of the two reasons the hard-deny rests on and leaves the
  other, that injected content must not force an eviction, untouched, so the agent published the
  number and changed nothing. Two corrections to the risk's own wording are worth reading with it,
  both in [ADR-0030](../adr/ADR-0030-brain-handoff.md)'s addendum of that date: the deny is the
  generic gated-tool branch shared by every gated tool rather than an escalation setting, and the
  recorded alternative keeps a taint refusal rather than removing one.
- **Whether screen capture should ship gated.** [ADR-0029](../adr/ADR-0029-vision-screen-capture.md)
  risk 2: capture is ungated, so an injected tool result can drive a capture in the turn it arrived
  in. The ADR says plainly that the user may reasonably overrule it, and names the paragraph to
  weigh when doing so.
- **The confusables fold table.** [ADR-0015](../adr/ADR-0015-output-guardrail.md) calls it
  "user-reviewable; the table is one edit to trim".
- **The completion chime.** The last genuinely open line of
  [design/overlay-ux.md](../design/overlay-ux.md) section 9; the rest of that section was settled by
  the 2026-07-03 and 2026-07-12 user passes, and the corner default is folded into
  [overlay-polish.md](overlay-polish.md).

## Not host work, but unblocked by user hardware

These are recorded in [refinements/](../refinements/index.md) and stay there, because each is a
design decision with a code cost and moving it would split it from its area. They are listed here
only so a sitting on the host's hardware knows what it could also settle:

- ~~**Co-residency** ([inference-model-manager.md](../refinements/inference-model-manager.md)):
  keeping CPU subagents serving through a swap, or a tiny GPU subagent beside the deep model. The
  brain-runs-alone rule is a v1 constraint of the 24 GB budget, first testable on a card that fits
  the tiers it would keep alive.~~ **Settled 2026-08-07 by the agent, in Docker against the real
  tiers**, so it was never host work in the end: `CORTEX_SWAP_CORESIDENT` landed off by default,
  the cortex and the deep model measured as not co-fitting (and, under WSL2, as silently paging
  rather than failing), and the deep model and the shipped subagent tier measured as fitting with
  908 MiB to spare (ADR-0030's co-residency addendum).
- **The Intel NPU as a third placement target**
  ([resource-governance.md](../refinements/resource-governance.md)): a feasibility pass, whose
  likely blocker is reachability from the dockerized WSL2 brain.
- **The spontaneous-pick nudge's live uptake** ([subagents.md](../refinements/subagents.md)):
  whether a live cortex reaches for distinct roster models unprompted, over real use rather than
  one scripted ask. The spawn tool is cortex-only and the small subagents do not respect prompt
  framing the way the cortex does, so no subagent-tier proxy tests it. **The scripted half ran
  2026-08-04**, and it ran here at the production 16K context with a single slot rather than the 4K
  its entry proposed, so this line's old claim that the hardware buys "real use at production
  context" is narrower than it was: the context is not what was missing. The scripted asks are
  answered (a prose-only ask never delegates at all; an invited one delegated in all 16 turns and
  piled the whole batch on one entry in all 16), and what is left for this hardware is the same
  question over months of real use rather than over 36 scripted turns.
- **Session-history summarization and the model-based reranker**
  ([session-history.md](../refinements/session-history.md),
  [memory.md](../refinements/memory.md)): both need `select` to go async first, and summarization
  needs its cache-versus-recompute question decided, which are the blockers that actually decide
  them; both are also model passes, which the host tier judges at production context.
  **Both blockers are gone as of 2026-08-06 and both passes shipped, so the sentence above is false
  about the tree and is kept only as the record of what was believed.** `RecallPolicy.select` and
  `HistoryWindow.select` are both `async` now, the recall one widened once for the reranker, the
  declined blended-relevance field and the recall trail together
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md)). The reranker is `JudgeRecallPolicy`
  (`CORTEX_MEMORY_RECALL=judge`) and summarization is `SummarizingHistoryWindow`
  (`CORTEX_HISTORY_SUMMARY`, now on by default), its cache question answered as cache rather than
  recompute, the account living in the session store and folded forward as the boundary moves.
  What is left of this line is the half that was always the honest one: both
  were measured on the agent's own runs, on one hand-built corpus each, so what this hardware still
  buys is the same judgment over real conversations rather than a blocker to clear. Their remaining
  entries say so at [session-history.md](../refinements/session-history.md) and
  [memory.md](../refinements/memory.md), and one of them was a decision for the user rather than
  work for anyone: the judge's default, whose only reason to be off was a cost that fell twenty
  times over on the same day. **That one was decided on 2026-08-08 and is no longer open**: the user
  asked for the turn cost before the flip, the flip followed the number (a recalling turn's time to
  first token rises 0.515 s, against a raw-versus-raw control whose interval spans zero), and
  `CORTEX_MEMORY_RECALL` ships as `judge`. What stays on this line is unchanged and is the same for
  both passes: the corpora are the agent's own, so real conversations are still what this hardware
  buys.
- **Unbalanced COM initialization on the blocking pool**
  ([body-gateway.md](../refinements/body-gateway.md)): the fix is code and stays there; the
  *observation* that would trigger it is the standing watch item in
  [windows-desktop.md](windows-desktop.md).

**The caveat on those three, resolved rather than left open (2026-07-19).** Each entry gave "the
cortex tier does not fit the 8 GB dev GPU" as part of its reason, and that clause is false:
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md) measured the cortex resident on the dev GPU
beside its projector at 4K on 2026-07-17 and drove a real turn through it the next day, and
[ADR-0030](../adr/ADR-0030-brain-handoff.md) records what that leaves, the model alone taking 7715
of the card's 8188 MiB. This page first recorded the clause as merely stale and reclassified
nothing, which left the question with whoever picked an entry up. It is settled here instead, per entry: the nudge probe
is agent-runnable and moved to actionable now; the two model passes were never hardware-blocked at
all, and their real blockers, the shared `select` widening and the undecided cache question, are
written at their entries and their origin ADRs. What genuinely wants this hardware is the same
judgment at 16K with more than one slot, which is a better answer rather than the only one, so all
three stay listed above as things a sitting here could also settle. **The nudge half of that last
sentence was overtaken on 2026-08-04**, when the probe ran on this hardware at 16K with the tier's
own single slot: what its entry still wants is duration, not context. **The other half was
overtaken on 2026-08-06**, when both of the model passes' named blockers, the shared `select`
widening and the undecided cache question, were cleared and both passes shipped, which is written
at the entry above. This paragraph's own verdict survives it and is worth restating for that
reason: neither pass was ever hardware-blocked, and what this hardware buys them is still judgment
over real use rather than a blocker to clear.
