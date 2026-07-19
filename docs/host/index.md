# Host-side work: index

Every piece of work only the maintainer can perform, one self-contained doc per sitting, extracted
from the ROADMAP's slice statuses on 2026-07-19 with the load-bearing wording kept verbatim. This
is the companion to [refinements/](../refinements/index.md) and the two hold different things:

- **[refinements/](../refinements/index.md) holds deferred *design*.** Work anyone can pick up once
  a seam, a consumer, or a decision unblocks it. Its entries describe code that is not written.
- **This directory holds work that is blocked on hardware the dev machine does not have.** The code is
  written; what is missing is a machine that can run it. Almost every item here is a *validation*,
  and the two that are not say so at the top of their section.

Neither is "host-only" in the [AGENTS.md](../../AGENTS.md) sense. An `integration`-marked live test
is host-only because it needs Docker, a GPU, or a network service, and gate 3 is explicit that "on
the host" **includes the agent**: those run here, in this repo, by whoever is working. An item
lands in this directory only when the agent's dev machine physically cannot do it.

## The two capabilities

Every item below carries one of two tags, and mixing them wastes a sitting:

| Tag | What it means | Why the dev machine cannot stand in |
| --- | --- | --- |
| **W** | A real Win32 desktop session, where the body runs natively | The dev machine is Linux under WSL2. Nothing OS native (COM, WinRT, GDI, a real Tauri IPC hop, a real window) exists to exercise. |
| **G** | A card that holds the real model tiers (24 GB) | The dev GPU is an 8 GB card. The cortex alone takes 7715 of 8188 MiB with `gemma-4-12b-it-qat-q4_0.gguf` loaded, so no tier pair, no ~31B model, and no GPU-placed subagent beside a resident cortex is reachable. |
| **W+G** | Both at once, in one session | Two items only: the end-to-end answer on the capture path, and a fully cortex-driven `set_volume`. |

**Tagged by capability, not by machine name, deliberately.** The repo's own evidence says the
Windows host and the 24 GB card are one laptop: [ARCHITECTURE.md](../ARCHITECTURE.md) says "Three
tiers share one 24 GB GPU", [ADR-0004](../adr/ADR-0004-model-lineup.md) says
"First real bring-up on the 24 GB card", and the 2026-07-01 Windows Tauri
validation ran "with the GPU brain up (`just up-gpu`, gemma-4-12B)", which does not fit 8 GB. But
**no document states it**, so the layout does not assume it. A capability tag is correct whether
that is one desk or two, and if it turns out to be two, only the tags need rereading and not the
directory. Settling this in writing is worth one sentence in an ADR the next time one is opened.

## The docs

| Doc | Tag | What one bring-up buys | Open |
| --- | --- | --- | --- |
| [windows-desktop.md](windows-desktop.md) | W | One `npm run tauri dev` beside a running brain: volume, the toast, the confirm card, the session commands, the reminder surface, the connection dot | 6 checks + 1 optional + 2 standing |
| [windows-capture.md](windows-capture.md) | W (one step W+G) | The screen-capture path, which needs its own switch, its own receipts, and its own expectations. Carries the single highest-consequence check in the repo | 1 check, 6 observations |
| [overlay-polish.md](overlay-polish.md) | W | The one item here that is **authoring, not validation**: the OS-window half of the overlay | 1 build (4 parts) + 1 design decision |
| [gpu-tier-scale.md](gpu-tier-scale.md) | G | The 24 GB machine: the deep-model pick and everything the pick unblocks, plus the measurements the placer and the caps ship without | 8 items |

User **decisions** (weigh, do not run) stay at their ADRs and are listed at the bottom of this
page rather than copied, so a decision has exactly one home.

## Why the split is by sitting

Three splits were considered and rejected before this one:

- **By machine.** Rejected for the reason above: no document says there are two, and the layout
  would encode an unverified premise where it is expensive to correct rather than in a tag where
  it is cheap. Two W+G items would also need duplicating or cross-referencing across the boundary.
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
  (`just up-gpu`); see [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md).
- `CORTEX_MODELHOST_BACKEND=supervisor` so the real `model-host` sidecar runs the tiers.
- `CORTEX_ESCALATION=1` for anything that swaps, plus `CORTEX_MODEL_FILE_BRAIN` once the pick
  exists. There is no deep-model pick yet, which is why the first item in
  [gpu-tier-scale.md](gpu-tier-scale.md) blocks four of the others.
- Enough free VRAM that the brain tier can be the only resident model (13 to 18 GB by estimate).

## Recommended order

Ordered by what unblocks the most, and grouped so each group is one sitting.

1. **The Windows desktop sitting** ([windows-desktop.md](windows-desktop.md)). One bring-up covers
   six checks. Start here because it is the cheapest and closes the most items at once, and because
   the confirm card and the toast are the two consent surfaces the safety posture rests on.
2. **The capture sitting** ([windows-capture.md](windows-capture.md)). Its own bring-up. Do the
   self-exclusion check first inside it and not last: if it fails, the loop it prevents is already
   live and the rest of the sitting is moot.
3. **The deep-model pick** ([gpu-tier-scale.md](gpu-tier-scale.md)). It gates the swap, the chaos
   kill, the timings, and the injection-harness run, so nothing else on the G side moves until it
   lands. It is also the longest single item here.
4. **The rest of the G list in one long sitting**, in the order that doc gives, since they share
   one bring-up and one blocker.
5. **The overlay polish** ([overlay-polish.md](overlay-polish.md)). A work session, not a sitting.
   It is authoring, it can fail review rather than fail a check, and it is the only thing here that
   is not urgent for correctness.

The two standing items in [windows-desktop.md](windows-desktop.md) never appear in this order:
one is an observation to make over months of real use, the other is a per-change obligation.

## Status convention

This is the one place this directory must **not** copy the refinements precedent. A refinement
lands or is declined; a user check can be attempted, inconclusive, and worth retrying. Each item
carries a status line, one of:

- **Never attempted.** The default, and what every item here says today.
- **Attempted YYYY-MM-DD, inconclusive:** with what happened. This is a real and useful state; an
  environment problem is not a failed check.
- **Done YYYY-MM-DD.** With the result written where the item's "Record it" line says.

## The exit contract

An item that completes writes its result back to its **origin ADR as a dated addendum** and into
its **runbook**, then leaves this directory. Same shape as a landed refinement, one difference:
refinements keep landed entries in place as the historical record of what a deferral became,
because their text often corrects its own ADR. A user check produces a *measurement*, whose home
is the ADR and the runbook, so this directory shrinks toward empty rather than accumulating.

Emptiness here is load-bearing: the ROADMAP gates the user-facing README on every slice, this
directory, and the refinements backlog all being clear.

## Decisions awaiting the user

Weighed, not run. Each stays at its ADR, which is the correct home for a decision; these are
pointers so they are not lost when the ROADMAP slims.

- **Five risks flagged for maintainer review** in
  [ADR-0030](../adr/ADR-0030-brain-handoff.md#risks-flagged-for-user-review): the gated-escalation
  default (a config plus one check to reverse), the model-host sidecar shape versus a docker-socket
  controller, the unmeasured brain-tier swap latency, two assistant messages under one turn id,
  and whether the brain phase should carry the cortex's full dispatcher.
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

- **Co-residency** ([inference-model-manager.md](../refinements/inference-model-manager.md)):
  keeping CPU subagents serving through a swap, or a tiny GPU subagent beside the deep model. The
  brain-runs-alone rule is a v1 constraint of the 24 GB budget, first testable on a card that fits
  the tiers it would keep alive.
- **The Intel NPU as a third placement target**
  ([resource-governance.md](../refinements/resource-governance.md)): a feasibility pass, whose
  likely blocker is reachability from the dockerized WSL2 brain.
- **The spontaneous-pick nudge's live uptake** ([subagents.md](../refinements/subagents.md)):
  whether a live cortex reaches for distinct roster models unprompted. No proxy exists, since
  gemma-12B does not fit 8 GB and the small subagents do not respect framing the way the cortex
  does.
- **Session-history summarization and the model-based reranker**
  ([session-history.md](../refinements/session-history.md),
  [memory.md](../refinements/memory.md)): both need `select` to go async first, and both are model
  passes that cannot be judged on 8 GB.
- **Unbalanced COM initialization on the blocking pool**
  ([body-gateway.md](../refinements/body-gateway.md)): the fix is code and stays there; the
  *observation* that would trigger it is the standing watch item in
  [windows-desktop.md](windows-desktop.md).
