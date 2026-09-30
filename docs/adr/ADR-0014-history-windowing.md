# ADR-0014: Session-history windowing as a character budget behind a `HistoryWindow` port

**Status:** Accepted (2026-08-06)

## Context

`TurnEngine` reads a session's **full** history from the `SessionStore` every turn. That is right
under the one hard rule (the store is the sole source of truth), but unbounded toward the model: a
long-lived conversation eventually exceeds the resident cortex's context window
(`CORTEX_CTX_SIZE`, 16K tokens on the deployed gemma-4-12B, [ADR-0004](ADR-0004-model-lineup.md)),
at which point llama-server refuses the request and the turn fails. This is
separate from **memory** ([ADR-0008](ADR-0008-memory-v1.md)), which is durable cross-session
recall; this ADR is about the in-context history of the current session only.

## Decision

1. **A pure `HistoryWindow` port in the core (`windowing.py`), injected through
   `TurnCapabilities.window`.** `async select(history, *, session_id, progress=None)` returns what
   one turn sends to the model; `None` in the slot keeps full-history behaviour byte for byte. The
   window applies at inference-message assembly only (its one caller is
   `assemble_inference_messages` in `turn_context.py`): the store keeps every message, and the
   window is computed fresh each turn, never stored, so there is nothing to rehydrate. A window
   returns a subsequence of the history in order and may additionally **prepend** derived context
   of its own, but may never drop or alter a message the window it wraps kept. `select` is `async`
   and takes `session_id` because a window may consult the store or the model, and a cached recap
   belongs to one session; `progress` is the stream's `ProgressSink`, passed per call because a
   sink belongs to one `Converse` stream while a window is a policy shared by every stream
   ([ADR-0038](ADR-0038-ranked-recall.md) decision 10). A heuristic window ignores both keywords
   and wraps a synchronous body.

2. **The base policy is `CharBudgetHistoryWindow(max_chars)`, a contiguous run of the newest
   turns.** Selection groups messages into turns (consecutive `turn_id`), walks from the newest
   turn backward, and stops at the first turn that would overflow the budget:
   - **turns are kept or dropped whole**, so the model never sees an assistant reply without the
     user message it answered;
   - **the kept slice is contiguous and ends at the newest turn**: the walk stops at the first
     overflow instead of skipping an oversized turn and collecting smaller older ones, because a
     gap in the middle of the history degrades the reply more than dropping the oldest turns does;
   - **the newest turn is always kept**, oversized or not, because the current user message must
     reach the model (a non-empty history never windows to an empty slice).

3. **Characters stand in for tokens.** The budget counts characters of message text, so the core
   needs no tokenizer and no I/O. On the cortex's tokenizer plain English is 4.7 characters a
   token and dense prose and source code 3.6 to 3.8, so a budget is sized on the dense ratio.

4. **`CORTEX_HISTORY_CHAR_BUDGET`, default `24000`, `0` disables it.** Read by `BrainRuntimeConfig`
   and wired by `build_history_window` (`window_builders.py`). It is **on by default**, because a
   long session's overflow is a correctness gap, and a setting that defaults off leaves it open in
   every deployment that does not set it. The default is sized on the whole prompt the cortex
   receives with the full tool stack ([readings](../readings/history-window.md#the-cortexs-whole-prompt)):
   24,000 characters is 5,008 gemma-4 tokens of plain English and at most 6,360 of the denser texts
   counted, and the security preamble ([ADR-0013](ADR-0013-untrusted-content.md)), the 23 tool
   schemas as the chat template renders them and the template's own tokens add 4,873. That leaves
   about 5,150 of the 16,384-token context for recalled memories, the recap, in-turn tool steps
   ([ADR-0009](ADR-0009-tools-mcp.md)) and the reply. At 48,000 the same prompt was 1,889 tokens
   over the context on dense text, so a long conversation would fail every turn once its newest
   turns filled the window. The budget stays in characters, one number for every deployment; one
   with fewer tools or a larger context may raise it.

5. **The turns the budget drops come back as a cached recap.** `SummarizingHistoryWindow`
   (`summarizing.py`) wraps the character-budget window and prepends at most one model-written
   account of the dropped prefix, cached in the `SessionStore` and extended as the boundary moves.
   It only prepends, so every failure path (store or model unreachable, a failed stream, an
   unusable reply) returns the character-budget selection byte for byte, which is what makes it
   safe on the turn's critical path. `CORTEX_HISTORY_SUMMARY` defaults to on and
   `CORTEX_HISTORY_RECAP_MIN_CHARS` sets how much newly dropped text is worth extending it for.
   Why a recap is cached rather than recomputed, how it is fenced, limited and announced, and why
   it does not spread taint are [ADR-0038](ADR-0038-ranked-recall.md) decisions 9 and 17 to 21.

6. **A model pass during selection finishes before the reply takes the GPU lease.** The inference
   adapter holds a non-reentrant lease for a stream's whole lifetime, and selection completes
   before the reply stream opens, so a window that finishes its own model call acquires and
   releases the lease ahead of the reply's acquire. A pass held open across the reply's acquire
   deadlocks, so selection-time inference goes through `drain_text` (`drain.py`), which closes the
   stream in a `finally` (ADR-0038 decision 8). The ordering was measured with three streams
   extending a recap at once over the real cortex: no hold overlapped another and every one
   released before its own reply acquired. The price is that extending a recap is one more hold
   every other stream's reply queues behind
   ([history recap readings](../readings/history-recap.md#folds-under-concurrent-streams)).

7. **A prompt the engine refuses as too long ends the turn with a note.** llama-server answers a
   prompt longer than its context with HTTP 400 and `exceed_context_size_error` before generating,
   and the inference adapter raises `ContextOverflowError`. The cortex's `handle_turn` catches it
   beside `MalformedToolCallError` ([ADR-0048](ADR-0048-generation-bounds.md) decision 14), flushes
   the guarded channels, streams and stores `CONTEXT_OVERFLOW_NOTE` under what the turn produced
   and completes, so the stream takes the next turn. No cap note follows, because the overflow is
   what ended the turn. The deep phase ends with `BRAIN_OVERFLOW_NOTE` the same way and re-raises,
   so the handoff settles `FAILED`. An escalation approved earlier in an overflowing cortex turn
   still runs, since a deployment may give the deep tier the larger context.

8. **The deep tier starts at the cortex's context, so both phases read the one budget.**
   `for_stream` in `engines.py` builds the deep phase's window from `CORTEX_HISTORY_CHAR_BUDGET`
   too, and `CORTEX_CTX_SIZE_BRAIN` defaults to 16384, the cortex's `CORTEX_CTX_SIZE`. A full
   window with the deep phase's 22 tools then leaves 5,521 to 6,873 tokens, the cortex's own
   margin; at 8192 the same prompt was 1.16 to 1.33 times the context
   ([readings](../readings/history-window.md#the-cortexs-whole-prompt)). At 16384 the pick stopped
   with a reply on 12 of 12 stop-row draws, where 8192 cut one mid-reasoning, and read 19,603 MiB
   above idle ([readings](../readings/history-window.md#the-deep-tier-at-16384)); it runs alone on
   the card ([ADR-0030](ADR-0030-brain-handoff.md) decision 8). A
   deep budget of its own was rejected: `SummarizingHistoryWindow` stores one recap a session and
   folds again from the start when the stored one covers more than the boundary, so a smaller
   deep window would store a recap past the cortex's boundary and the cortex's next turn would
   fold the whole dropped prefix again. A deployment that lowers `CORTEX_CTX_SIZE_BRAIN` lowers
   `CORTEX_HISTORY_CHAR_BUDGET` with it, which shortens the cortex's window too.

## Consequences

- Long sessions no longer grow past the model's context. What the budget drops is the oldest turns,
  whole and predictably, and with the summary on they return as a recap; the stored history and
  memory keep everything.
- A single oversized newest turn is sent whole and can still overflow the model context: the window
  limits history, not one turn's size, and such a turn ends with the note of decision 7. Long
  recalled memories and large tool results reach the same note. A per-turn input cap would be a
  decision at the overlay, not silent truncation here.
- At 16384 the pick decoded the same tokens at 0.86 of its 8192 rate, the two drawn on different
  nights, so whether the larger context slows decode is open
  ([R-757](../refinements/tasks/757-measure-whether-the-deep-tiers-16384-context-slows-decode.md)).
- The `EchoInferenceBackend` reply counter counts user messages in the *windowed* history, so its
  `"reply {n}"` script diverges from the stored count only past the budget, which CI-sized tests
  never reach.
- A tokenizer-backed exact window would fit the same port with no engine change.

## Alternatives rejected

- **Token-exact windowing.** Exact counting needs the model's tokenizer (llama-server's
  `/tokenize`), which puts I/O or a model-specific vocabulary inside the pure core for precision
  the headroom buys more cheaply.
- **A budget in tokens with a per-deployment ratio.** The ratio varies more between texts on one
  tokenizer (3.6 to 4.7 characters a token on gemma-4) than between the two tokenizers counted, so
  a deployment would still set the dense ratio, and the pair restates a character budget with one
  more setting.
- **Keeping 48,000 and relying on the note.** With the tool stack a full dense window alone is over
  the cortex's context, and the window keeps the newest turns, so every later turn of that
  conversation would end in the note instead of dropping its oldest turns to the recap.
- **Last-N-turns.** Its unit is disconnected from the real constraint: N turns of one-liners and N
  turns of pasted logs differ by orders of magnitude in tokens.
- **Recomputing the recap every turn.** One full generation ahead of every reply, against one per
  boundary move (ADR-0038 decision 9).

## Related

- Module contracts: [brain-core.md](../modules/brain-core.md),
  [brain-orchestrator.md](../modules/brain-orchestrator.md).
- Readings: [history recap](../readings/history-recap.md),
  [history window tokens](../readings/history-window.md).
- [ADR-0038](ADR-0038-ranked-recall.md) (the recap's design and the selection-time lease rule),
  [ADR-0008](ADR-0008-memory-v1.md) (cross-session memory).
