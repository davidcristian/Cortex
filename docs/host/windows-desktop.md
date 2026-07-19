# The Windows desktop sitting (tag W)

Seven checks that share one bring-up, plus two standing items that never close. Everything here is
OS native: a real Win32 window, real COM and WinRT calls, and a real Tauri IPC hop. The dev machine is
Linux under WSL2, so none of it can be stood in for; see [index.md](index.md) for why that is the
only thing these have in common.

The seventh is numbered **0**, because it is the bring-up itself and every other check rides on it.
It was added on 2026-07-19 and the numbering of the rest is deliberately untouched, since ADRs cite
these by number.

**The bring-up, once, for all seven.** Prerequisites are in [index.md](index.md). Then:

```powershell
$env:CORTEX_SEAM_TOKEN = "<the same secret the brain serves with>"
$env:CORTEX_BODY_ADDR  = "0.0.0.0:50151"
cd body\app
npm run tauri dev
```

with the brain up beside it. Add `-f docker/docker-compose.body.yml` to the compose command so the
brain can dial back (`CORTEX_BODY_BACKEND=grpc`), and `-f docker/docker-compose.gpu.yml` for the
real cortex. Full procedure: [runbooks/body-overlay.md](../runbooks/body-overlay.md) section B.

Order inside the sitting: check 0 (it is the bring-up), then volume and the toast (they exercise
the brain to body direction and the firewall crossing, so a failure there explains failures later),
then the confirm card, then the three read surfaces.

---

## 0. The bring-up itself: the hotkey, the tray, show and hide, and one streamed turn

**Status: never attempted.** Tag **W**.

**What only this proves.** That `os_windows` really registers a system-wide hotkey on a live Win32
desktop, that the tray item and window show/hide work, and that the `converse` Tauri command
streams a live brain turn into the webview across the real IPC hop. Everything under it is gated:
the chord parser is pure and 100% covered in `body_core`, and the overlay's streaming reducer is
covered in `body/app`. What no gate reaches is a real registration against a real desktop that
other software is also competing for.

**Why it is a numbered check and not just a heading.**
[ADR-0011](../adr/ADR-0011-body-v1.md)'s Host-Windows addendum names "the `os_windows`
`global-hotkey` registration, the tray, and window show/hide" and "the real `converse` command
streaming a live brain turn to the webview" as two of its six lines, and until 2026-07-19 neither
had a check here. [AGENTS.md](../../AGENTS.md)'s three-records rule held forward from every item in
this directory and failed backward from that ADR. This is the fix, and the reason it reads as
obvious work is the reason it went missing: it is what you do before the checks, so nobody wrote
it down as one.

**Do.** [runbooks/body-overlay.md](../runbooks/body-overlay.md) section B, validation steps 1 to 3.
Press **Ctrl+Alt+Space** from some other foreground application; press it again to hide. Use the
tray's **Show overlay**. Type a prompt, watch the reply stream, then send a follow-up that depends
on the first (the session is shared across turns).

**Pass.** The overlay appears from any foreground app and toggles away again; the tray item does
the same; a typed turn streams token by token rather than arriving whole, and a follow-up keeps
context.

**Fail, and what each failure means.**
- The hotkey never fires: something else owns the chord. It is configurable (`CORTEX_HOTKEY`,
  default `ctrl+alt+space`, parsed by `body/app/src-tauri/src/hotkey.rs`, which falls back to the
  default and prints on an unparseable value), so try another chord before calling it a defect.
- The overlay appears but no text arrives: the seam, not the desktop. `UNAUTHENTICATED` means the
  shell and the brain disagree on `CORTEX_SEAM_TOKEN`; a red connection dot means the brain is not
  reachable at `CORTEX_BRAIN_ADDR`.
- The whole reply arrives at once: the stream is being buffered somewhere, which is a finding about
  the IPC hop rather than about the brain, since the brain's deltas are gated on both sides.

**Record it.** A dated addendum to [ADR-0011](../adr/ADR-0011-body-v1.md) against the two lines
named above; then delete this section.

---

## 1. The real Core Audio volume action

**Status: never attempted.** Tag **W**.

**What only this proves.** That `WindowsAudioControl`'s narrowly authorized `unsafe` COM path
actually drives the endpoint, and that a container reaches the host body **through the Windows
firewall**. The agent proved the container to host dial on 2026-07-08, but against a Linux gRPC
server under WSL2 native dockerd; the Windows crossing is the untested half of ROADMAP assumption
3. Nothing in CI builds this backend at all.

The two paragraphs below were the ROADMAP's status for this work. They were **preserved here when
the ROADMAP was slimmed on 2026-07-19** and are no longer in that file, so this doc is their only
home; the live statement of the same obligation is
[ADR-0023](../adr/ADR-0023-body-gateway-volume.md)'s "Host-Windows (host-only)" paragraph and its
2026-07-08 addendum ("Remaining for the slice: only the **Host-Windows** half").

> **Host-authored (host-validated on Windows, never in CI).** The real `WindowsAudioControl`
> (Core Audio, `cfg(windows)`, the `windows` crate; `unsafe` for COM authorized narrowly to
> `os_windows` by ADR-0023, the one crate opting out of the workspace `unsafe_code = forbid`), and
> the Tauri shell's `body_server::start()` binding `CORTEX_BODY_ADDR` and serving on Tauri's
> runtime.

> **Remaining:** only the **Host-Windows** real Core Audio validation ("set volume to 30%"), per
> [body-volume.md](../runbooks/body-volume.md). The **agent-Docker** dial across the container
> boundary is done (2026-07-08, [ADR-0023 addendum](../adr/ADR-0023-body-gateway-volume.md)): the
> tokened round-trip passed from a container and the untokened dial was rejected. On an 8 GB GPU
> the gemma-4-12B cortex does not fit, so a fully *cortex-driven* `set_volume` is bounded by what
> fits; the seam + gateway + tool path validated directly.

**That last sentence is stale, and this item was mistagged for it (corrected 2026-07-19).** It
first read as needing a 24 GB card for the cortex-driven half, which would have made this item
**W+G**. The VRAM clause is false: [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) measured
the real `gemma-4-12b-it-qat-q4_0.gguf` fitting the 8 GB dev GPU **beside its projector** at
`--ctx-size 4096 --parallel 1` on 2026-07-17 and drove a real vision turn through the shipped
inference adapter on 2026-07-18. The 11.3 GB reservation the sentence leaned on is a 16K-context
figure. What no card can supply is the Win32 desktop the audio backend needs, so the whole item is
**W**, and one bring-up closes the cortex-driven half with it. (Second correction, 2026-07-19:
this paragraph also cited a cortex-driven tool call "here on 2026-07-03", which was agent-run on
the 24 GB card, the machine the agent had then. The dev-card evidence is the vision turn.)

**Do.** [runbooks/body-volume.md](../runbooks/body-volume.md), "Host-only half (real Core Audio on
Windows)", three numbered steps. Then say or type **"set volume to 30%"**, and **"what's my
volume?"** for `get_volume`.

**Pass.** Host output volume moves. No approval card appears, because volume is ungated by design
(reversible). `get_volume` answers with the real level.

**Fail, and what each failure means.**
- `UNAUTHENTICATED: invalid or missing seam token`: the shell and the brain disagree on
  `CORTEX_SEAM_TOKEN`.
- The assistant says it could not reach the body: the dial failed. Either the firewall blocked the
  port or `CORTEX_BODY_ADDR` bound loopback only. A dead body is a recoverable `is_error` by
  design, so this fails as an honest sentence rather than a crash.
- The tool never fires: the cortex did not emit it. Not a body failure.
- The call succeeds and nothing moves: this is the interesting failure, and it is the COM path.

**Record it.** A dated addendum to [ADR-0023](../adr/ADR-0023-body-gateway-volume.md), whose
2026-07-16 addendum on moving the sync OS calls off the async worker ends its "Validated" paragraph
with "Unchanged and still host-side: the real 'set volume to 30%' on Windows" (later addenda follow
it, so search for the sentence rather than reading the file's end); a note in
[runbooks/body-volume.md](../runbooks/body-volume.md); then delete this section.

---

## 2. A real reminder toast

**Status: never attempted.** Tag **W**.

**What only this proves.** That WinRT toasts render at all for an unpackaged app's
`AppUserModelID`, and that the CI-gated inert-text and escaping rules survive the real notification
service. Everything except "does it appear and read well" is already gated in `body_core`.

Kept verbatim from [refinements/scheduling.md](../refinements/scheduling.md), where this lived
inside the landed `Notify` entry:

> Remaining, and unchanged from what this slice always owed: the **Host-Windows** look at a real
> toast (runbook [scheduling.md](../runbooks/scheduling.md)).

and from the ROADMAP's Slice 9.5 status:

> the port plus the inert-text rule are gated in `body_core`, `WindowsNotify` renders a WinRT
> toast, and only the user's look at a real toast is left.

**Do.** [runbooks/scheduling.md](../runbooks/scheduling.md), "Host-only half on Windows", four steps.
In short: *"remind me to stretch in one minute"*, then a second reminder whose text contains
`<b>bold</b> & "quotes"`.

**Pass.** A toast appears carrying the reminder text; summoning the overlay afterwards shows **no**
card for it, because a shown toast is delivery and the ticker acked it. The hostile-markup reminder
appears with those characters literal.

**Fail.** No toast at all is most likely the app identity, not the code: a `npm run tauri dev` run
carries no Start Menu shortcut and so no registered `AppUserModelID`. The runbook gives the
borrowable PowerShell id for `CORTEX_TOAST_APP_ID` to confirm that diagnosis. A toast that never
appears **only for the markup reminder** is the sharp failure: the escaping broke and the payload
did not parse. Clicking a toast doing nothing is expected, not a failure (toast activation routing
is a recorded deferral).

**Record it.** A dated addendum to [ADR-0025](../adr/ADR-0025-scheduling-reminders.md), whose
host line names the native toast; then delete this section.

---

## 3. The confirm card through real Tauri IPC

**Status: never attempted.** Tag **W**.

**What only this proves.** That the `ConfirmRoute` compare-and-clear and the `confirm_response`
command carry an answer back into a **live** turn over the real IPC transport. The card itself was
validated in Chrome on 2026-07-08 (approve, deny, multi-turn) and the confirm exchange was proven
over a real loopback gRPC wire on both answers; neither reaches the Tauri IPC hop.

The ROADMAP said this in a slice status that was slimmed away on 2026-07-19; the wording that is
still live is [ADR-0022](../adr/ADR-0022-email-write-confirmer.md)'s 2026-07-08 addendum:

> **Still pending (genuinely OS-native, host-only):** the **Windows Tauri confirm-card**
> validation (hotkey → gated send → card → approve/deny through the real IPC transport). It is the
> one piece Chrome/Docker can't reach, exactly as ADR-0013 predicted.

The runbook for it is [body-overlay.md](../runbooks/body-overlay.md). The same obligation is
stated once more in [refinements/untrusted-content.md](../refinements/untrusted-content.md):

> Only the Windows-native validation of the card remains host-side.

**Do.** [runbooks/body-overlay.md](../runbooks/body-overlay.md) section B, validation step 4. Ask
for a gated action (a send, with `CORTEX_EMAIL_SEND_ENABLED=true` and the Bridge reachable, or any
name you put in `CORTEX_TOOLS_GATED`). Approve. Repeat and deny. Repeat and **ignore** it.

**Pass.** Approve runs the action and the turn continues. Deny returns the declined message and
nothing happens. Ignoring it denies on timeout (default 120 s) and the reply says the user
declined. A card arriving while the overlay is minimized surfaces the preview, and that preview
does **not** auto-fade while the question is open.

**Fail.** A card that appears and whose answer never reaches the brain is the IPC hop failing, the
exact thing this check exists for. A turn that proceeds *without* an answer would be a gate bypass
and is the one failure here that is a security finding rather than a bug.

**Record it.** A dated addendum to [ADR-0022](../adr/ADR-0022-email-write-confirmer.md), whose
"Still pending (genuinely OS-native, host-only)" paragraph names exactly this; then delete this
section.

**Note on where this is recorded.** It originates at ADR-0022 but its backlog line lived under
[refinements/untrusted-content.md](../refinements/untrusted-content.md) rather than
`email-confirmer.md`, which is worth knowing when searching for it.

---

## 4. The session-read Tauri commands

**Status: never attempted.** Tag **W**. **Until 2026-07-19 this was recorded in exactly two places,
both of them prose, and one of them was about to be cleaned.**

**What only this proves.** That the two ungated glue commands carry the reads across the real IPC
hop. Both ends are already proven: the brain half was Docker-validated against real Redis on
2026-07-07, and the overlay reducer is gated at 100%.

The paragraph below was the ROADMAP's status for that slice; it was **preserved here when the
ROADMAP was slimmed on 2026-07-19** and is no longer in that file. The live one-line form is
[ADR-0021](../adr/ADR-0021-session-read-seam.md)'s 2026-07-07 addendum, "the Windows-native Tauri
`list_sessions`/`session_messages` commands remain host validation":

> **Host half (host-validated on Windows):** the `list_sessions`/`session_messages` Tauri commands
> (`src-tauri/src/sessions.rs`), the same ungated-glue class as the `converse` command. **Cold
> start opens a new chat**; prior chats are reachable via the switcher/cycling (auto-restore
> deferred).

The parenthetical is stale and is kept only because the sentence is quoted: **auto-restore landed
2026-07-12** ([refinements/session-read-seam.md](../refinements/session-read-seam.md)). Expect the
most recent chat to restore, not a blank one.

**Do.** In the running overlay: open the switcher with the header's **Recent chats** button (the
two overlapping speech bubbles), or `Ctrl+K` from the keyboard, then `Ctrl+↑`/`Ctrl+↓` to cycle.
Restart the app and summon again. **Corrected 2026-07-19:** this line named the `⌄` control, which
is the header's rightmost button and dismisses the overlay (`TuckIcon`, "tuck it away"), so
following it literally ended the check instead of starting it.

**Pass.** The switcher lists prior chats with their derived titles and previews, most recent first;
cycling moves through them and loads each one's history; a restart restores the most recent chat.

**Fail.** An empty list against a brain that has sessions is the IPC hop or the seam token. A list
that appears but whose messages never load is `session_messages` specifically.

**Record it.** A dated addendum to [ADR-0021](../adr/ADR-0021-session-read-seam.md), whose
2026-07-07 live-validation addendum closes with "the Windows-native Tauri
`list_sessions`/`session_messages` commands remain host validation" (many later addenda follow
it, so search for the sentence rather than reading the file's end); then delete this section.

---

## 5. The reminder pull surface on the live hotkey path

**Status: never attempted.** Tag **W**. **Until 2026-07-19 it had no backlog line**, though it was
never unrecorded: [ADR-0025](../adr/ADR-0025-scheduling-reminders.md)'s host line has named "the
overlay's reminder surface on the real hotkey→overlay path" since the slice landed, and the
procedure is in the runbook. What it lacked was a place that listed it as work still owed.
(Corrected 2026-07-19: this section first claimed the runbook paragraph was its only record, which
its own "Record it" line below refutes.)

**What only this proves.** That the browser-validated card stack reads correctly at real window
size, and that a failed pull is a no-op on the live path rather than an emptied surface.

Kept verbatim from [runbooks/scheduling.md](../runbooks/scheduling.md), which carries the procedure:

> what is genuinely host-side is the real hotkey path: whether the stack reads well over the live
> window and whether killing the brain mid-session leaves the cards in place (it should: a failed
> pull dispatches nothing) rather than emptying the surface.

**Do.** Summon the overlay with something due. Read the stack. Then stop the brain (`just down`)
and summon again.

**Pass.** The card stack sits above the history; each card carries its text, how long ago it fired,
`repeats` on a recurring series, and a dashed, faintly red-tinted `untrusted source` badge when
tainted. Dismissing a card acks it. With the brain down, the cards stay.

**Fail.** Cards vanishing when the brain goes away means a failed pull is clearing state, which is
the specific regression this check exists to catch.

**Record it.** A dated addendum to [ADR-0025](../adr/ADR-0025-scheduling-reminders.md), whose
host line already names "the overlay's reminder surface on the real hotkey→overlay path"; then
delete this section.

---

## 6. The connection indicator's real IPC hop

**Status: never attempted.** Tag **W**. **Until 2026-07-19 this was recorded in one place only, a
runbook paragraph.**

**What only this proves.** The `check_link` command across the real IPC hop. The classification
itself is gated in `body_core::link` and checked against a real brain by the `body-rpc` live suite,
so Windows adds the hop and nothing else.

**Do.** [runbooks/body-overlay.md](../runbooks/body-overlay.md) section B, validation step 5.

**Pass.** Green on summon with the brain up. Stop the brain and summon: red within the retry budget,
staying red and re-checking every 5 s while the panel is open. Start the brain: green on its own,
without a re-summon, and the chat list fills in with it. Point at a live brain with the **wrong**
`CORTEX_SEAM_TOKEN`: amber, because the brain answered `Unauthenticated` and so is reachable and
refusing.

**Fail.** A dot that never leaves green is the honest-signal failure the ADR-0011 addendum was
written to avoid: an always-green dot is chrome that means nothing.

**Record it.** A dated addendum to [ADR-0011](../adr/ADR-0011-body-v1.md); then delete this
section.

---

## Standing: unbalanced COM initialization on the blocking pool

**Status: standing observation, never closes on its own.** Tag **W**.

Not a check to run. Both Windows backends call `CoInitializeEx(COINIT_MULTITHREADED)` per call and
never `CoUninitialize`, which on tokio's blocking pool means threads join the MTA and are later
reaped unbalanced. Only a long-uptime Windows session with sporadic OS actions can show it.

The fix and the argument for it stay in
[refinements/body-gateway.md](../refinements/body-gateway.md), which is where the code cost
belongs; what lives here is the trigger, kept verbatim from that entry:

> **Fix when it bites**, the trigger being any COM failure or thread growth the user sees on
> Windows after a long session

**Watch for.** A volume or toast call that starts failing after the app has been up for a long
time, or Tauri's thread count growing without bound.

**Record it.** If it ever bites, say so on that refinements entry, which then becomes actionable.

---

## Optional, and a different bring-up: PGDATA directly on the Windows drive

**Status: never attempted.** Tag **W**, but no Tauri app and no overlay: this needs only Docker on
the Windows host. Explicitly a nice to have, not a default.

Kept verbatim from [ADR-0008](../adr/ADR-0008-memory-v1.md) decision 7:

> **Durable data placement: named volume + export, not a raw PGDATA bind mount.** The live
> Postgres data directory is a **named Docker volume** (avoids the ownership/latency pitfalls of a
> Postgres data dir over a Docker-Desktop Windows bind mount); a dump/sync job exports it to
> `D:\Software\AI\Database` to satisfy the plug-and-play requirement. Mounting PGDATA directly onto
> the Windows drive is validated on the host as a *nice to have*, not the default. The plug-and-play
> guarantee does not depend on it.

**What only this proves.** Whether Postgres can run its data directory over the Windows bind mount
at all. Nothing depends on the answer: the plug-and-play guarantee rides the dump sidecar either
way, which is why this sits at the bottom of the list.

**Do.** Point PGDATA at a Windows bind mount instead of the named volume and bring the memory
override up. [runbooks/memory-pgvector.md](../runbooks/memory-pgvector.md) records the intent but
carries no procedure, so writing one is part of this if it is ever taken.

**Pass.** Postgres initializes and serves with acceptable latency.

**Fail.** Ownership errors on initdb, or latency bad enough to notice. Both are the documented
pitfalls and both mean the default stays the default, which is a perfectly good result to record.

**Record it.** A dated addendum to [ADR-0008](../adr/ADR-0008-memory-v1.md) and a line in
[runbooks/memory-pgvector.md](../runbooks/memory-pgvector.md).

---

## Standing: the toolchain-linked full build

**Status: standing obligation, per change rather than once.** Tag **W**.

CI checks `cargo fmt` on both ungated Rust trees and runs a cross-target clippy that type-checks
`os_windows` without linking. Only a Windows build links them.

Kept verbatim from [refinements/repo-gates.md](../refinements/repo-gates.md):

> a toolchain-less build, by contrast, is out of reach, so the "build" third of the risk ADR-0011
> named stays host-side

**What this means in practice.** Any change touching `body/crates/os_windows` or
`body/app/src-tauri` is unproven until it has been built on Windows once. The gates catch format
and type errors; they cannot catch a link error.

**Do, once per such change** (this was the only item in this directory carrying no command,
added 2026-07-19, and it is the one repeated most often):

```powershell
cd body/app
npm run tauri build
```

The shell declares `os-windows` under `[target.'cfg(windows)'.dependencies]`, so a Windows build
of the shell is what links both ungated trees at once. The `npm run tauri dev` that every check
above starts with links them too, so a sitting that ran those has already covered whatever change
it was carrying; the build command is the form to use when there is no sitting to attach it to.

**Pass.** It links and the app starts.

**Fail.** A link error, which is exactly the third of the risk the gates cannot reach. Record it
where the change was made, not here.
