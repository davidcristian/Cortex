# ADR-0014: Session-history windowing as a char-budget tail behind a `HistoryWindow` seam

- **Status:** Accepted (Slice 3 deferred refinement, landed 2026-07-03)
- **Date:** 2026-07-03

## Context

`TurnEngine` reads a session's **full** history from the `SessionStore` every turn and hands
all of it to the backend. That is correct under the one hard rule (the store is the sole source of
truth), but unbounded toward the model: a long-lived conversation eventually exceeds the
resident cortex's context window (`CORTEX_CTX_SIZE`, 16K tokens on the deployed gemma-4-12B,
ADR-0004/0007), at which point llama-server truncates or errors and the turn degrades
unpredictably. The gap was recorded at Slice 3 in the ROADMAP deferred-refinements list
("windowing / truncation / summarization"). This is distinct from **memory** (ADR-0008),
which is durable *cross-session* recall. This ADR is about the *in-context* history of the
current session only.

## Decision

1. **A pure `HistoryWindow` seam in the core (`windowing.py`), injected via
   `TurnCapabilities.window`.** `select(history) -> Sequence[Message]` returns the slice of
   the stored history one turn sends to the model; `None` (the default) keeps today's
   full-history behavior byte for byte. The window applies at **inference-message assembly
   only**. Persistence is untouched: the store keeps every message, the window is derived
   fresh each turn, never stored, nothing to rehydrate (the one hard rule is unaffected).
   Like `memory` and `tools`, the capability slot keeps the engine's constructor within its
   dependency ceiling, and any future policy (summarization above all) drops into the same
   seam without touching `SessionStore` or `TurnEngine`.
2. **The shipped policy is `CharBudgetHistoryWindow(max_chars)`, which is a turn-aligned contiguous
   tail.** Selection groups messages into turns (consecutive `turn_id`), walks from the
   newest turn backward, and stops at the first turn that would overflow the budget:
   - **turns are kept or dropped whole**, so the model never sees an assistant reply without
     the user message it answered;
   - **the kept slice is a contiguous tail** because the walk stops at the first overflow rather
     than sieving old small turns past a big one, because a gap mid-history confuses the
     model more than honest truncation;
   - **the newest turn is always kept**, oversized or not, because the current user message must
     reach the model (the window never returns an empty slice for a non-empty history).
3. **Characters stand in for tokens.** The budget is counted in characters of message text
   (roughly 4 chars/token for English) so the core needs no tokenizer and no I/O. It is a
   deliberately conservative heuristic, not an exact fit. Deployments size it well under
   the model context.
4. **Config: `CORTEX_HISTORY_CHAR_BUDGET`, default `48000`, `0` disables.** Read by
   `BrainRuntimeConfig` and wired by `build_history_window` at the composition root. It is
   **on by default**: the deferral is a correctness gap under long sessions, and a knob
   nobody sets fixes nothing. 48K chars ≈ 12K tokens of history against the 16K-token
   cortex context, leaving ~4K tokens of headroom for the security preamble (ADR-0013),
   recalled memories (ADR-0008), tool schemas and in-turn tool steps (ADR-0009), and the
   reply itself.

## Alternatives rejected

- **Token-exact windowing.** Exact counting needs the model's tokenizer, an adapter/engine
  concern (llama-server's `/tokenize`) that would put I/O or a model-specific vocabulary
  inside the pure core, for precision the headroom margin buys more cheaply. If exactness is
  ever needed, a tokenizer-backed `HistoryWindow` adapter fits the same seam.
- **Last-N-turns.** Simpler to state but its unit is disconnected from the real constraint:
  N turns of one-liners and N turns of pasted logs differ by orders of magnitude in tokens.
- **Summarization (compress old turns instead of dropping them).** The richer option and the
  original deferral names it. But it changes content (a lossy model pass inside turn
  assembly), needs inference and therefore the GPU path, and deserves its own design.
  **Still deferred**, recorded in the ROADMAP (Slice 3 block); it will land behind this same
  `HistoryWindow` seam.

## Consequences

- Long sessions stop growing toward the context wall; what the model loses is the oldest
  turns, wholesale and predictably, while the stored history (and Slice 5 memory) keeps
  everything, so recall can still surface dropped context.
- A single oversized newest turn is sent whole and can still overflow the model context because
  the window bounds history, not one turn's size (a per-turn input cap would be a UX
  decision at the overlay, not silent truncation here).
- The `EchoInferenceBackend` reply counter counts user messages in the *windowed* history,
  so the `"reply {n}"` script diverges from the stored count only past the budget, which is
  unreachable in CI-sized tests, irrelevant on the real backend.
- The seam invites exactly the follow-ons planned: summarization, or a tokenizer-backed
  exact window, each a drop-in `HistoryWindow` with no engine change.
