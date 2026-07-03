# Audit of Slice 8 (Body v1: hotkey → overlay → chat)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Every code-level claim in the Slice 8 section checks out against the tree: BrainTransport::converse with the typed TurnEvent mirror and TransportError::Protocol (body/crates/core/src/transport.rs), the one-turn/half-close body_rpc adapter with full loopback contract tests including SeamError→Failed and empty/early-close→Protocol (body/crates/rpc/src/converse.rs + tests/converse.rs), the fully-tested Hotkey port and Accelerator::from_chord (body/crates/core/src/os.rs + tests), the os_linux/os_macos coverage(off) stubs with reasons, the cfg(windows) global-hotkey backend, the 100%-thresholded Vitest overlay with its own path-filtered CI job (ADR-0006 addendum), the typechecked TauriBridge, and the cortex-body Tauri shell (tray, hidden window, hotkey toggle + cortex:activate, converse over a Tauri Channel) outside the gated workspace. The Windows end-to-end validation is properly paper-trailed (ROADMAP dated 2026-07-01, body-overlay.md runbook, #[ignore]-marked live seam test) and is statused verified-as-documented. The consciously deferred overlay polish (transparent+click-through window, screen-corner morph, hide-on-blur, tighter CSP) is recorded exactly where the slice says (overlay-ux.md §4 and the runbook) but, uniquely among the done slices, it has no entry in the ROADMAP's central 'Deferred refinements & later work' ledger and no ADR-0011 record, which AGENTS.md gate 4 requires; plus two minor stale-text drifts in the ADR-0011 addendum (a 'frontend/' subdirectory that doesn't exist, and a bridge-port sketch with onActivate/hide/connection-status that the implemented converse-only BrainBridge supersedes). The implementation is complete and validated; the verdict is 'undocumented-gaps' solely on these low-severity documentation-convention findings.

## Claims checked (18)

- **📄 verified-as-documented (host-only run; paper trail checked)**. Slice 8 status 'done': hotkey → overlay → chat validated end to end on Windows against the real brain (gemma-4-12B), host-validated 2026-07-01 via `npm run tauri dev` + `just seam-health`
  - Evidence: docs/ROADMAP.md:249,280-286 records the run and date; docs/runbooks/body-overlay.md:24-67 describes the Windows bring-up and the 3-step validation; live seam test body/crates/rpc/tests/live.rs:39-41,58-60 is #[ignore]-marked (the Rust integration marker per its module doc lines 1-9); justfile:109-110 (`seam-health` runs `cargo test -p body-rpc --test live -- --ignored`)

- **✅ verified.** BrainTransport::converse streams a typed TurnEvent turn; TurnEvent mirrors proto ServerEvent (Delta/ToolActivity/Status/Complete/Failed) and TransportError gained a Protocol variant
  - Evidence: body/crates/core/src/transport.rs:55-85 (TurnEvent enum), 42-43 (TransportError::Protocol), 119-124 (converse(session_id,&str) -> impl Stream<Item=Result<TurnEvent,TransportError>>); drop-to-cancel contract documented at lines 111-118

- **✅ verified**. body_rpc adapter over the generated bidi Converse: one turn per call with half-close, SeamError→Failed, empty oneof / early close→Protocol, non-OK status split Connection/Rpc
  - Evidence: body/crates/rpc/src/converse.rs:24-34 (single ClientEvent then end-of-stream = half-close), 61-67 (SeamError→TurnEvent::Failed), 68-74 (empty oneof→Protocol), 101-105 (stream ends before TurnComplete→Protocol), 87-89/107-109 (statuses via status_to_error); body/crates/rpc/src/client.rs:84-105 (transport-sourced status→Connection, else Rpc)

- **✅ verified.** Contract tests script the fake brain over loopback covering every converse branch
  - Evidence: body/crates/rpc/tests/converse.rs:29-45 (six scripts), 170-265 (echo happy path proving session_id/text transmission, PartialThenError→Failed, EmptyEvent→Protocol, EarlyClose→Protocol, RejectCall→Rpc, MidStreamError→Rpc), served on 127.0.0.1:0 (lines 138-149); Connection mapping covered in tests/client.rs:146-188 (connection refused, brain death after connect, invalid address)

- **✅ verified.** Hotkey port + pure Accelerator::from_chord chord→KeyboardEvent.code mapping in body_core, fully tested
  - Evidence: body/crates/core/src/os.rs:39-49 (Hotkey trait), 65-79 (Accelerator::from_chord), 84-129 (letters/digits/F1-F24/named-key code mapping); tests: body/crates/core/tests/os.rs (8 tests incl. supported keys, UnsupportedKey rejection, canonical modifiers, register success/failure via a fake backend) and tests/hotkey.rs (20 tests over parse/canonicalize/Display)

- **✅ verified**. os_linux / os_macos are unimplemented!() stub crates proving the #[cfg_attr(coverage, coverage(off))] escape-hatch policy with inline reasons
  - Evidence: body/crates/os_linux/src/lib.rs:10 (crate-root feature gate), 18 (coverage(off)), 24 (unimplemented! with reason); body/crates/os_macos/src/lib.rs:10,18,24 identical; body/Cargo.toml:27-29 declares cfg(coverage) via check-cfg; policy documented in docs/modules/body-os.md:22-30

- **✅ verified**. os_windows real global-hotkey backend behind the Hotkey port, cfg(windows)-gated, keeps unsafe_code=forbid, host-only (never in CI)
  - Evidence: body/crates/os_windows/src/lib.rs:12-16 (whole crate cfg(windows)); src/windows.rs:22-94 (GlobalHotKeyManager registration, Accelerator→Modifiers/Code mapping, listener thread filtering by id + Pressed edge); body/Cargo.toml:26 (unsafe_code=forbid workspace lint); its live behavior is the user's documented host validation (docs/runbooks/body-overlay.md:71-74, ROADMAP:280-283)

- **✅ verified**. React overlay is 100%-gated: Vitest + v8 with 100% lines/branches/functions/statements thresholds, run by just check-overlay folded into just check
  - Evidence: body/app/vite.config.ts:19-37 (thresholds {lines:100,branches:100,functions:100,statements:100}; only main.tsx, tauriBridge.ts, demoBridge.ts, test-setup, vite-env excluded); justfile:74-77 (check-overlay: npm ci + typecheck + test:cov), justfile:23-31 (parallel inside `just check`)

- **✅ verified**. The overlay has its own path-filtered CI job per the ADR-0006 addendum (third toolchain dimension, body/app/ → overlay-only before body/ → rust)
  - Evidence: .github/workflows/ci.yml:127-145 (overlay job gated on changes.outputs.overlay, setup-node cached on body/app/package-lock.json, runs just check-overlay); scripts/ci_paths.py:25-31 (three-dimension verdicts, ALL/DEFAULT fail-closed), 43-56 (body/app/ OVERLAY_ONLY rule ordered before body/); docs/adr/ADR-0006-gate-performance.md:91-105 (addendum dated 2026-07-01)

- **✅ verified**. TauriBridge typechecks against @tauri-apps/api and is the coverage-excluded glue; components depend only on the BrainBridge port
  - Evidence: body/app/src/bridge/tauriBridge.ts:1-42 (imports Channel/invoke from @tauri-apps/api/core, implements BrainBridge over a Tauri Channel with drop-to-cancel); tsconfig.json include:["src"] + package.json typecheck (tsc --noEmit) run by check-overlay; body/app/src/bridge/types.ts:6-32 (TurnEvent/TransportError TS mirror + BrainBridge port); vite.config.ts:30 excludes it from coverage only

- **✅ verified**. Tauri shell body/app/src-tauri (cortex-body): tray + hidden window, hotkey → toggle + cortex:activate, converse command streaming TurnEvents to the webview over a Tauri Channel, outside the gated workspace
  - Evidence: body/app/src-tauri/Cargo.toml:2 (name cortex-body), 11 ([workspace] own root); body/Cargo.toml:5 (exclude=["app"]); tauri.conf.json:14-27 (label overlay, visible:false, alwaysOnTop, skipTaskbar); src/lib.rs:16-18 (OVERLAY_LABEL, ACTIVATE_EVENT "cortex:activate"), 36-47 (toggle_overlay show/hide + emit); src/tray.rs:9-26; src/converse.rs:86-112 (#[tauri::command] converse streaming WireMessage {event}|{error}); frontend wiring body/app/src/main.tsx:28-32 + components/App.tsx:30-31

- **✅ verified.** Configurable hotkey (CORTEX_HOTKEY, default ctrl+alt+space) and CORTEX_BRAIN_ADDR at the app; registration failure is non-fatal and logged
  - Evidence: body/app/src-tauri/src/hotkey.rs:41-52 (CORTEX_HOTKEY parse with default fallback), 16-28 (errors logged to stderr, tray still summons); body/crates/core/src/hotkey.rs:153-161 (default ctrl+alt+space); src-tauri/src/converse.rs:14-15,92 (CORTEX_BRAIN_ADDR, default http://127.0.0.1:50051)

- **✅ verified**. docs/runbooks/body-overlay.md exists and describes both the browser (fake-bridge) loop and the Windows Tauri validation
  - Evidence: docs/runbooks/body-overlay.md:1-86. Section A browser dev (DemoBridge self-summon, just check-overlay), section B Windows prerequisites/icons/run + 3-step end-to-end validation, Notes on what's proven vs user's, v1 window behaviour deferrals, CSP, hotkey-collision fallback

- **✅ verified.** Deferred overlay polish (transparent window + click-through margins together, OS-window morph to a real screen corner, hide-on-blur, tighter CSP) is recorded in overlay-ux.md §4 + body-overlay.md
  - Evidence: docs/design/overlay-ux.md:129-137 ('v1 window scope (Slice 8)' inside §4. Transparent window with click-through 'to be done together', screen-corner morph, hide-on-blur); docs/runbooks/body-overlay.md:75-81 (same list + 'CSP is null for v1; tighten it once…'); matching code state: tauri.conf.json:22 transparent:false, :30 csp:null

- **✅ verified**. Module docs body-app.md, body-os.md, body-core.md, body-rpc.md exist and cover the slice's contracts
  - Evidence: docs/modules/body-app.md:1-53 (BrainBridge port, converse command WireMessage contract, activate seam, config, invariants); docs/modules/body-os.md:1-38 (per-platform backends + escape-hatch policy); docs/modules/body-core.md:8,30-44 (TurnEvent, Protocol variant, converse signature); docs/modules/body-rpc.md:21-23 (converse translation)

- **✅ verified.** ADR-0011 exists with the six decisions and the 2026-07-01 addendum reversing decision 6 (overlay gated at 100% + browser-validated; only the real bridge module excluded)
  - Evidence: docs/adr/ADR-0011-body-v1.md:27-94 (decisions 1-6: one turn per Converse, TurnEvent mirror + Protocol, Hotkey first cfg-gated backend, global-hotkey crate, app outside gated workspace, React+Vite), 141-169 (addendum: gate, testability seam, browser validation, pointer to overlay-ux.md)

- **✅ verified**. Refined from the host run: the light/dark toggle moved into the panel header
  - Evidence: body/app/src/components/Panel.tsx:16-22. The <header className="head"> contains the onToggleTheme button (aria-label "Toggle theme"); Panel.test.tsx covers the component under the 100% gate

- **✅ verified.** Gate proven: cfg-gated OS backends and the stub coverage escape-hatch policy
  - Evidence: Only the target-matching crate compiles (os_windows/src/lib.rs:12 cfg(windows); os_linux/os_macos compile everywhere as stubs); coverage(off) hatch with inline reasons at os_linux/src/lib.rs:18-24 and os_macos/src/lib.rs:18-24; body/Cargo.toml:27-29 check-cfg declaration; policy write-up docs/modules/body-os.md:22-30

## Gaps (3)

### G1 · severity low · documented (docs/ROADMAP.md:284-286 (Slice 8 paragraph), docs/design/overlay-ux.md:129-137 (§4 'v1 window scope'), docs/runbooks/body-overlay.md:75-81 (Notes))

The overlay polish itself is not implemented (deliberate deferral): the window is opaque (tauri.conf.json transparent:false) with no click-through margins, the orb sits at the window's own corner rather than a real screen corner, there is no hide-on-blur (hotkey toggles), and the CSP is null (tauri.conf.json:30).

### G2 · severity low · **not documented as a deferral**

The overlay-polish deferral has no entry in the ROADMAP's central 'Deferred refinements & later work' ledger (docs/ROADMAP.md:451-565 contains subsections for Slices 2/3/5/6/6.5/4/8.5 and cross-cutting, but none for Slice 8/ADR-0011) and no deferral record or addendum in ADR-0011 itself. AGENTS.md gate 4 calls that section 'the one place none is lost' and requires every consciously deferred refinement to be recorded there (and at its origin ADR). The deferral is well written down elsewhere (slice paragraph, overlay-ux.md §4, body-overlay.md), so nothing is actually lost, but the repo's own ledger convention is broken for this slice alone.

**Adversarial re-check: confirmed.** The auditor is correct. The 'Deferred refinements & later work' ledger (docs/ROADMAP.md:451-565) has per-slice subsections for Slices 2, 3, 6, 6.5, 5, 4, 8.5 and a cross-cutting block, but no Slice 8/ADR-0011 subsection, and grep of the ledger range for the polish items (transparent window, click-through margins, screen-corner morph, hide-on-blur, tighter CSP) finds no entry. ADR-0011 itself (read in full) records no such deferral: its only addendum (lines 141-169) reverses decision 6 to gate the overlay frontend, and its Risks section covers different items (one-turn Converse, hotkey conflicts). A repo-wide grep of docs/adr/*.md for the polish terms returns nothing relevant. The deferral is written down only in the Slice 8 progress paragraph (docs/ROADMAP.md:284-286), docs/design/overlay-ux.md:132-136, and docs/runbooks/body-overlay.md:76-80, all outside the central ledger and outside the origin ADR, so per AGENTS.md gate 4's convention ('recorded at its origin ADR and collected here so none is lost', ROADMAP.md:453-455) the ledger convention is indeed broken for this slice, even though the deferral itself is not lost. Git history confirms no later commit added a ledger entry.

### G3 · severity low · **not documented as a deferral**

Stale text in the ADR-0011 addendum vs the shipped code: (a) it describes 'a frontend/ (Vite + React + TypeScript) project under body/app/' but the Vite project lives directly at body/app/ (src/, package.json at the root, no frontend/ subdirectory); (b) it sketches the bridge port as 'converse(...), onActivate, hide, connection status' but the implemented BrainBridge (body/app/src/bridge/types.ts:30-32) has only converse. Activation arrives as the cortex:activate DOM event, there is no hide method, and no connection-status surface exists in the overlay. docs/modules/body-app.md documents the real contract correctly, so the drift is mildly misleading only to a reader of the ADR alone.

**Adversarial re-check: confirmed.** The auditor is correct on both halves. (a) The ADR-0011 addendum's "frontend/ project under body/app/" does not match the shipped layout. The Vite project sits directly at body/app/ with no frontend/ subdirectory, and every other artifact (justfile check-overlay recipe, ADR-0006 path classifier, CI docs) references body/app/ directly. (b) The addendum's bridge sketch (converse + onActivate + hide + connection status) is wider than the shipped BrainBridge, which exposes only converse; activation arrives as the cortex:activate DOM event, there is no hide method, and no connection-status surface exists (the design doc's connection dot is unshipped target design). docs/modules/body-app.md documents the real contract, so the drift misleads only an ADR-alone reader, but no written record anywhere acknowledges or defers correcting it: the ROADMAP deferred-refinements ledger has no Slice 8/ADR-0011 entry, ADR-0011 has no correcting note after the addendum, and the Slice 8 close-out deferrals (overlay-ux.md §4, body-overlay.md) cover OS-window polish (transparency, click-through, hide-on-blur, corner morph, CSP), not this documentation drift. The gap stands as undocumented.
