# Rust and TypeScript strings are outside the prose check

**Status:** done 2026-09-23
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)

The prose check reads string literals in Python only: every non-test module under `scripts/` and
under a brain package's `src/` (decision 16 of
[ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)). Rust and TypeScript sources are outside
it, so the strings they print keep words the table in AGENTS.md bans. A survey on 2026-09-22 used
decision 16's rule on every tracked `.rs`, `.ts` and `.tsx` file outside generated code: a
double-quoted literal holding a space, with paths and flags masked, matched with `bannedwords`. It
found 75 hits in 34 files, 9 in non-test sources and 66 in tests.

The 9 in non-test sources:

- Four errors that call the gRPC connection `seam`: `the capture is too large for the seam even
  downscaled` in `body/crates/core/src/os/screen.rs`, `malformed seam message` in
  `body/crates/core/src/transport.rs`, `invalid seam token` in `body/crates/rpc/src/client.rs` and
  `the capture is too large for the seam` in `body/crates/rpc/src/screen.rs`.
- The body server's refusal, `invalid or missing seam token` in `body/crates/rpc/src/auth.rs`. The
  brain's refusal in `cortex_orchestrator/auth.py` became `invalid or missing token` on 2026-09-22,
  so the two sides now word one refusal two ways. No code reads either text, because both sides act
  on the `UNAUTHENTICATED` status code. [body-volume](../../runbooks/body-volume.md) and host task
  [H-002](../../host/tasks/002-core-audio-volume-action.md) quote the body's wording, which is still
  what the body prints.
- `the frame is ... but carries ... bytes` in `body/crates/core/src/os/screen.rs`, and the body
  server's `Unimplemented` reply, `input injection lands in a later slice`, in
  `body/crates/rpc/src/server.rs`.
- Two lines of the overlay's demo conversation in `body/app/src/bridge/demoScript.ts`, `Sending is
  gated` and `the seam PR`, which a user of the demo reads.

In tests, most hits are test names and assertion messages. One is printed on every `just check`:
the `#[ignore]` reason `live seam check` on the live Rust suites, which `cargo test` shows for each
ignored test.

Three names stay whatever this task decides: `CORTEX_SEAM_TOKEN`, the `x-cortex-seam-token` header
and the `cortex.seam.v1` proto package, which decision 15 keeps because the Windows host and the
wire depend on them.

**What would close it.** Either extend the literal reader to `.rs`, `.ts` and `.tsx` files and
rewrite what it finds, or record in decision 16 why those sources stay outside. The Python reader
takes its literals from `ast`. `scripts/` has no Rust or TypeScript parser, so a reader there needs
a tokenizer that knows raw strings, byte strings, template literals and comments, or a parser
dependency. Rewriting the body's refusal to match the brain's also changes the runbook and host
task that quote it.

## History

- 2026-09-22: opened after the overnight run's summary named the gap, with the survey above as its
  first reading.
- 2026-09-23: done. The survey held at HEAD: 75 hits in 34 files, 9 in non-test sources. The
  premise that a reader needed a new tokenizer did not hold: `slashcomments.py` already lexed raw and
  byte strings, char literals, lifetimes, template literals and regex literals to find comments.
  It now records each string's text too, and `proseliterals.py` reads the non-test Rust and
  TypeScript files under `body/` with it, as decision 16 of
  [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md) now states. The nine strings were
  rewritten, the body's refusal now reads `invalid or missing token` like the brain's, and the
  live suites' `#[ignore]` reason reads `live gRPC check`. Tests stay outside, as they do for
  Python.
