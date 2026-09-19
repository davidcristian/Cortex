# ADR-0011: Body v1, from hotkey to overlay to chat over the first OS backend

**Status:** Accepted (2026-09-19)

## Context

The first host-native body slice is a Tauri app that summons an overlay on a global hotkey, sends
the typed prompt to the brain over `Converse`, and renders the streamed reply. It is where the
first `cfg`-conditional OS backend and the coverage exemption for its stubs arrive, so most of what
follows is about where logic lives and what the checks can and cannot see.

CI is Linux and GPU-less, and `check-body` requires 100% line, region and branch coverage across
the body workspace. A Tauri app is a GUI with a webview and a real OS event loop, none of it
measurable headless on Linux. The roadmap anticipated this: app wiring stays thin, logic lives in
`body/crates/core`, and Tauri glue that resists measurement gets a narrowly scoped exclusion
recorded in an ADR. This ADR is that exclusion, and the checks that grew around it.

## Decision

1. **One turn per `Converse` call.** `BrainTransport::converse(session_id, text, decisions)` opens
   a fresh `Converse` stream per prompt and streams the reply. Session continuity is already
   external (the one hard rule: the brain rehydrates from `SessionStore`), so every prompt shares
   the `session_id` and nothing is multiplexed on the client. The call's client stream stays open
   past its `UserTurn` only to answer a `ConfirmRequest` mid-turn
   ([ADR-0022](ADR-0022-email-write-confirmer.md)). Cancellation is dropping the returned stream.
   The brain already handles several turns per stream and `Cancel` end to end, freeing the model
   lease; what is deferred is body-side and coupled, several turns per call and the client sending
   `Cancel`, since on a one-turn call a `Cancel` then a half-close ends with no terminal event,
   which the adapter reads as `Protocol`. Today the overlay's Stop denies a pending confirm and
   mutes the sink but does not abort the RPC, so the brain finishes and persists the full turn
   ([R-127](../refinements/tasks/127-multi-turn-and-proto-cancel.md)).

2. **`TurnEvent` is a typed core mirror of the proto `ServerEvent`, and one stream reports both
   kinds of failure.** In `body_core::transport::turn`: `Delta`, `ToolActivity`, `ToolOutcome`,
   `Status`, `ConfirmRequest`, `ConfirmResolved`, `Complete` and `Failed`. The stream item is
   `Result<TurnEvent, TransportError>`, split by origin as `health` is: a brain-reported `SeamError`
   mid-turn is `Ok(TurnEvent::Failed)` (the connection is fine, this turn failed); an unreachable
   brain or a non-OK status is `Err`, and wire data the adapter cannot interpret (an empty oneof, a
   stream ending before `TurnComplete`) is `TransportError::Protocol`. The overlay renders the two
   differently and iterates one stream.

3. **`Hotkey` is the first `cfg`-conditional OS backend; Windows is real, macOS and Linux are
   stubs.** The port and the pure `HotkeyChord` to accelerator conversion live in `body_core`,
   fully tested. The backends live in per-platform crates `os_windows`, `os_linux` and `os_macos`,
   each `#[cfg(target_os = ...)]`, and only the matching crate compiles. On Linux CI that is
   `os_linux`, whose `unimplemented!()` bodies have `#[cfg_attr(coverage, coverage(off))]` with an
   inline reason: the coverage exemption this slice existed to demonstrate. `os_windows` makes real
   OS calls, so it is a thin adapter validated on the host, never in CI.

4. **The Windows `Hotkey` backend wraps `global-hotkey`, keeping `unsafe_code = "forbid"`.** Raw
   `RegisterHotKey` and a message pump would need `unsafe`; the crate encapsulates it and delivers
   activations on a channel. If wiring its delivery into Tauri's event loop proves awkward, the
   fallback is Tauri's `global-shortcut` plugin behind the same `Hotkey` port.

5. **The Tauri app is a host-native shell outside the checked workspace.** `body/app/src-tauri` is
   its own Cargo workspace root, path-depending on `body/crates/{core,rpc}` and `os_windows`, and
   `body/Cargo.toml` excludes it, so `just check` never builds Tauri and the coverage step never
   sees it. Its Rust is thin wiring: tray, hidden window, `#[command]` handlers, forwarding the
   `TurnEvent` stream to the webview. Every branching decision (accelerator conversion, event
   mapping, the transport, link classification) lives in `body_core` or `body_rpc`, which stay at
   100% coverage. Config at the app: `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`) and
   `CORTEX_HOTKEY` (default `ctrl+alt+space`, configurable because it may collide; a registration
   failure reaches the overlay).

6. **The overlay is React + Vite, at 100% coverage and validated in a browser.** The Vite project
   lives at `body/app/`, tested with Vitest and Testing Library, coverage by v8 at 100% line,
   branch, function and statement, run by `just check-overlay` inside `just check` and by its own
   path-filtered CI job ([ADR-0006](ADR-0006-check-performance.md)). Components never call Tauri:
   they depend on the `BrainBridge` port, whose real implementation (`tauriBridge.ts`) wraps
   `invoke` and `listen` and is, with `main.tsx`, the only source excluded from coverage. A fake
   bridge drives tests, and a demo bridge drives `vite dev` in a plain browser, so the prompt,
   stream and render path is validated without Windows. The design source of truth the components
   are built against is [docs/design/overlay-ux.md](../design/overlay-ux.md); later appearance
   decisions live in [ADR-0031](ADR-0031-bubble-mark.md) (the mark),
   [ADR-0034](ADR-0034-panel-views.md) (panel views) and
   [ADR-0035](ADR-0035-console-and-motion.md) (console, scrollbars in decision 22, and the header
   row in decision 23: the title's inset is 10px, with 27px clearances).

7. **A summon is recorded state, not a one-off event.** The shell re-dispatches the host hotkey as
   a `cortex:activate` DOM event, and the browser build summons itself on load. A plain dispatch
   reaches only listeners that already exist, and the app attaches its listener in a passive effect
   that React flushes after paint, so an early summon was lost: the dev self-summon every time, and
   a hotkey press during a cold webview mount. `overlay/activation.ts` records a request
   (`requestActivation`) and the app takes any outstanding one when its listener attaches
   (`takePendingActivation`); both paths consume it, so a remount cannot replay an answered summon.

8. **The connection indicator is derived, not polled.** A `Health` poll on a timer spends a request
   every interval for a tray app's whole uptime, mostly while hidden, and is still stale between
   ticks. The indicator uses three sources instead: every `TurnEvent` proves the brain is serving
   and every `TransportError` that it is not; one probe on each summon's rising edge (the
   `useSummonEffect` latch); and a recheck every `LINK_RECHECK_MS` (5000 ms) only while the overlay
   is visible and the link is not ready, so the steady state sends nothing. The recheck is an
   interval keyed on "visible and unhealthy" with an in-flight guard, because a timeout restarted
   when `probing` goes false dies after one retry whenever the probe answers inside one React
   batch. The probe runs through the retrying transport
   ([ADR-0024](ADR-0024-transport-retry.md)), so one probe is also the reconnect attempt.

   Four states: `ready` (answered, ready), `degraded` (answered and not serving: `ready = false`,
   any non-OK status, an unreadable reply), `down` (`TransportError::Connection`, nothing answered)
   and `unknown` (not yet asked). Whether a probe is in flight is a modifier (`LinkView.probing`)
   that pulses the dot without changing its colour, and a routine summon probe on a ready link does
   not show at all. `body_core::link` classifies (`LinkStatus::from_health`, `from_error`) and
   `probe_link` never fails, a failure being the answer; the shell's `check_link` is infallible for
   the same reason, reporting even a bad `CORTEX_BRAIN_ADDR` as `down` with the reason.
   `components/LinkDot.tsx` renders tone and a label that is both tooltip and accessible name, from
   an `ok`, `warn`, `bad` trio taken from the theme palette. `Health` answers `ready = false` while
   a model handoff holds the GPU ([ADR-0030](ADR-0030-brain-handoff.md)), which shows amber between
   turns; a pushed status stream waits for a consumer
   ([R-129](../refinements/tasks/129-streamed-brain-status.md)).

9. **The shell and `os_windows` are format- and lint-checked where each can be.** `os_windows` is a
   `body` workspace member, so `cargo fmt --all --check` covers it already (rustfmt never evaluates
   `cfg`), and `check-body` clippies it for `x86_64-pc-windows-msvc`, which type-checks without an
   MSVC toolchain because clippy never links. `check-body` also runs `cargo fmt --check` on the
   shell, and `scripts/ci_paths.py` gives `body/app/src-tauri/` both the rust result and a `shell=`
   output of its own. The toolchain-linked build of either tree stays on the host
   ([H-011](../host/tasks/011-toolchain-linked-full-build.md)).

10. **The shell is clippied by `just check-shell`, which CI runs and `just check` does not.** It is
    the one recipe outside the single command, because it needs system packages a clean dev box
    need not have: the Linux GTK, webkit and dbus `-dev` packages for the host run (five roots,
    `--no-install-recommends`) and a resource compiler for the Windows one. Inside `just check` it
    would make that command unrunnable on such a box; a check that skipped itself when the
    libraries were missing could not fail, and one that failed for a missing library would train
    people to ignore failures. The recipe holds the check, so CI's path-filtered `shell` job (on
    the `shell=` output) and a developer run the same thing. A shell clippy finding can therefore
    reach a local commit and be caught in CI instead of at the hook. The cost is about a minute on
    the change that could break it ([readings](../readings/shell-clippy.md)). A check whose
    evidence, rather than toolchain, is out of reach does not join it
    ([ADR-0067](ADR-0067-image-volume-record.md) decision 1). Nothing else may join it.

11. **`check-shell` runs clippy twice, for the host and for `x86_64-pc-windows-msvc`.** The host run
    configures out every `#[cfg(windows)]` item (the real `start` and `DEFAULT_BODY_PORT` in
    `body_server.rs`, the real hotkey registration), and the Windows run configures out the stubs,
    so the two lines cover complementary halves of the same files and sit in one recipe. The
    Windows run needs none of the Linux `-dev` roots, but `tauri_build` compiles a VERSIONINFO
    resource for every Windows target through `tauri-winres` and `embed-resource`, which panics
    without a resource compiler. The recipe sets `RC_x86_64_pc_windows_msvc`, defaulting to
    `/usr/bin/x86_64-w64-mingw32-windres` from `binutils-mingw-w64-x86-64`, and it must be a path:
    windres derives its preprocessor from its own `argv[0]`, and a bare name off `PATH` makes it
    run a prefixed gcc that is not installed. `llvm-rc` was rejected: no rustup component includes
    it, the package that does is several times larger, and its preprocessing path wants a `cl.exe`
    stand-in. The resource object is never read, since clippy does not link
    ([R-599](../refinements/tasks/599-the-shells-windows-clippy-waits-on-a-resource-step.md)).

12. **The line limit covers the overlay's TypeScript and the decision records, and three files stay
    outside it.** `scripts/linecap.py` scans `.py`, `.rs`, `.ts` and `.tsx` with one limit of 300
    lines, since the limit is about reading load and not about toolchains. A test file is whatever
    that toolchain's runner collects: `*.test.ts`, `*.test.tsx` and the Vitest `setupFiles` entry
    `test-setup.ts` are exempt, while a `.d.ts` is hand-written TypeScript and is not. `dist` and
    `coverage` are skipped as build output. Outside the limit by decision:
    `body/app/src/overlay.css`, one cascade whose order has meaning, so splitting it trades length
    for fragile `@import` ordering ([R-011](../refinements/tasks/011-stylesheet-outside-line-cap.md));
    `index.html`, a single mount point; and `proto/body.proto`, because limiting it would
    contradict the invariant that the wire contract is defined once in that file.
    `scripts/tests/test_linecap.py` asserts all three, so dropping one is a deliberate edit. An
    overlay module over the limit is split, never exempted. The same walk limits every markdown
    file to 250 lines, because a document is read whole to learn what it says: one over the limit
    says two things, or contains measurements that belong in a readings record. The two backlog
    indexes are the only exception, and each is exempt only while it still contains the comment
    `just backlog` writes above the block it generates, so an index somebody starts maintaining by
    hand stops being exempt. Each rule needs at least one file to pass, so a tree with no markdown
    in it fails the scan instead of leaving the rule idle.

## Consequences

- The checks cover `body_core`, `body_rpc`, the stubs and the overlay; what they do not cover is
  the Tauri shell and `os_windows`, which are held to fmt and the clippies above and validated on
  the host. The exclusion is safe only while the shell stays thin, so branching logic moves into
  the covered crates.
- **Host-only**, each with its check in [docs/host/](../host/index.md): hotkey registration, the
  tray, window show and hide, and a real `converse` streaming to the webview
  ([H-001](../host/tasks/001-bring-up-and-streamed-turn.md)); `confirm_response` into an open turn
  and the session reads ([ADR-0021](ADR-0021-session-read-rpcs.md), ADR-0022); `check_link`'s IPC
  hop ([H-008](../host/tasks/008-connection-indicator-ipc-hop.md)); the OS window polish, which is
  authoring rather than validation: a transparent window with click-through margins, the morph to a
  real screen corner, hide on blur and a tighter CSP
  ([H-014](../host/tasks/014-os-window-polish.md)); and the toolchain-linked build of the shell and
  `os_windows` on every change to them
  ([H-011](../host/tasks/011-toolchain-linked-full-build.md)).
- The `shell` CI job has never run on a runner, Actions being off for this repository
  ([R-300](../refinements/tasks/300-shell-job-never-ran-on-a-runner.md)).
- Readiness beyond liveness shows only between turns: a streamed turn event sets the dot green.

## Alternatives rejected

- **A long-lived bidirectional `Converse` per overlay**: client-side multiplexing to model and test
  for nothing that drop-to-cancel does not already cover.
- **Raw Win32 `RegisterHotKey`**: needs `unsafe` against the workspace `forbid`.
- **Polling `Health` on a timer**: costs a request per interval while hidden and is stale between
  ticks.
- **Shell clippy inside `check-body` or `just check`**: puts a webkit install on every `body/`
  change, or makes the single command unrunnable on a clean box.
- **A shell clippy that skips itself**: a check that cannot fail.
- **Excluding a TypeScript module from the limit by glob**: configuration that enumerates loosely
  has failed open here before; an overlay module is split instead.

## Related

- Modules: [body-core](../modules/body-core.md), [body-rpc](../modules/body-rpc.md),
  [body-os](../modules/body-os.md), [body-app](../modules/body-app.md),
  [repo checks](../modules/repo-checks.md).
- Runbook: [body-overlay](../runbooks/body-overlay.md); design:
  [overlay-ux](../design/overlay-ux.md).
- Readings: [shell clippy](../readings/shell-clippy.md).
- ADRs: [ADR-0006](ADR-0006-check-performance.md) (path filtering),
  [ADR-0023](ADR-0023-body-gateway-volume.md) (the brain to body direction),
  [ADR-0035](ADR-0035-console-and-motion.md) (overlay appearance),
  [ADR-0067](ADR-0067-image-volume-record.md) (evidence out of reach).
