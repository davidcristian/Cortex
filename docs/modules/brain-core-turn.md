# brain/packages/core: one conversation turn

Part of [`cortex_core`](brain-core.md), which holds the shared values, the public surface rule and
the package invariants. This document covers everything that runs while the user waits: the turn
engine, the history the model is shown, session titles and listings, and the filter over what the
reply says. Memory and recall are in [brain-core-memory.md](brain-core-memory.md),
tools in [brain-core-tools.md](brain-core-tools.md), delegated work in
[brain-core-subagents.md](brain-core-subagents.md), and the model swap in
[brain-core-residency.md](brain-core-residency.md).

## Ports

- `TurnRunner` provides `handle_turn(session_id, text, *, turn_id) -> AsyncGenerator[TurnEvent]`:
  one user turn as a stream of domain events, and the boundary between the orchestrator's stream
  plumbing and whichever engine serves the turn, which is why the servicer's engine factory is
  typed to it rather than to `TurnEngine`. **The runner is told which turn it is serving**
  (ADR-0046 decision 9): a turn that fails emits no completion to read the id off.
- `SessionStore` is the source of truth for conversation state and survives model swaps and
  restarts: `append(session_id, message)`, `history(session_id)` (append order, empty when
  unknown), `list_sessions(*, limit)` (most recently active first), `set_title(session_id, title)`
  (a display title `list_sessions` prefers over the first-message derivation, ADR-0021 decision 9),
  `delete(session_id)` (removes a whole chat, its history, title, recency entry and hoisted
  membership, idempotent and needing no tombstone), `set_hoisted(session_id, *, hoisted)` (ADR-0021
  decision 12), and `set_recap(session_id, recap)` / `recap(session_id)` for the cached history
  recap below. Fake: `InMemorySessionStore`; adapter: `cortex_session`.
- `InferenceBackend` provides
  `stream(model, messages, *, tools=(), schema=None, bounds=None) -> AsyncIterator[InferenceEvent]`:
  one stateless streamed completion. `model` is a logical id (ADR-0004), and **an implementation
  answers only for the ids it serves**, failing with `InferenceError` on one it does not
  (ADR-0068 decision 8). `schema` constrains decoding to a JSON Schema (ADR-0028). `bounds` is a
  `GenerationBounds(max_tokens, thinking, trace_tokens)` (ADR-0048), where `thinking=False` is a
  request to the chat template and **not a guarantee** (ADR-0049), so an implementation passes it
  on, never enforces it, and lets a trace that arrived anyway cross as `ReasoningChunk`, the
  caller's only evidence the switch did not work; `trace_tokens` is the half the engine applies,
  `0` ending the thought at once and `None` leaving the tier's `--reasoning-budget` deciding, and
  the two are independent. A completion closes with one `DecodeStop` and one `DecodeCadence` when
  the engine reports them, in that order, after the text they describe and before any tool calls.
  The promises are the shared list in `inference/tests/stream_contract.py`, driven over the fake
  and the llama.cpp adapter alike. Fakes: `EchoInferenceBackend` (shipped wiring for a GPU-less
  deployment, streaming `"reply {n}: {text}"` where `n` counts the user messages in the stored
  history) and `ScriptedInferenceBackend` (one event list per `stream` call, a `calls` tally,
  `fail_with`, and a `serves` set of ids it answers for).
- `PreferenceStore` provides `all()` and `set(key, value)` (ADR-0032): the user's settings as
  opaque pairs this side never parses, where an empty value clears the key. It holds no
  conversation content, so it sits outside the one hard rule. Fake: `InMemoryPreferenceStore`.

## The turn engine

`TurnEngine(store, backend, clock, *, cortex_model=DEFAULT_CORTEX_MODEL,
capabilities=TurnCapabilities())` (`engine.py`) is pure orchestration over the ports.
`DEFAULT_CORTEX_MODEL` is the logical id `"cortex"`; deployments override it through
`CORTEX_MODEL_CORTEX`, read by the composition root.

`handle_turn(session_id, text, *, turn_id)` is an async generator. It routes through `route_turn`,
builds the user `Message` from the clock and the id it was given, appends it to the store, runs the
inference and tool loop over the stored history, yields one `TextDelta` per streamed chunk, then
persists the assistant `Message` and yields one `TurnCompleted`. Closing the stream part way
(`aclose()`) keeps the persisted user message, does not persist the partial reply, and closes the
abandoned backend stream. A backend failure surfaces as `InferenceError` after the user message
was persisted, with one exception that **ends** the turn instead of failing it (ADR-0048): a
`MalformedToolCallError` says the unparsable fragment is the model's own tokens, so that path
flushes the guarded channels, streams the note the `StopLedger` picks, logs a warning naming the
session and the turn, and persists once.

`TurnCapabilities(memory=None, tools=None, window=None, guardrail=None,
record_tainted_memory=False, generate_titles=False, progress=None, escalation=None, bounds=None,
residency=None)`
(`turn_context.py`, with the context assembly `assemble_inference_messages`) is the frozen bundle
of everything optional about a turn. With the bare default the turn is plain streamed inference.

- `memory` (a `MemoryRecaller`, ADR-0008): before inference the engine recalls the top
  `DEFAULT_RECALL_K` (5) memories for the user text within the turn's scope and prepends any hits
  as a `Role.SYSTEM` message that is never stored. A recalled memory marked `tainted` is fenced
  with the turn nonce, taints the turn (ADR-0019) and names its own record id as the turn's source.
  After the reply it records the exchange, unless the turn read untrusted content. **Memory that
  cannot be reached costs the turn its notes and not the turn** (ADR-0008 decision 12):
  `EmbedderError` and `MemoryStoreError` are caught on both halves and nothing else is, a failed
  read logging a warning and one `StatusUpdate`, a failed write logging an error and saying
  nothing.
- `record_tainted_memory` (ADR-0019) governs writing only: with it on, a tainted turn is recorded
  with `tainted=True` instead of being dropped, and a stored tainted memory is fenced on recall
  either way.
- `tools` (a `ToolDispatcher`, ADR-0009) adds `SECURITY_PREAMBLE` and runs the shared tool loop
  with a fresh `TaintLedger`; the loop's messages are not persisted. `window` (a `HistoryWindow`,
  ADR-0014) selects what part of the stored history one turn sends, leaving persistence untouched.
- `guardrail` (an `OutputGuardrail`, ADR-0015) passes every assistant delta through one turn's
  filter. The scrubbed text is what streams, completes **and** persists: the reply on record is the
  reply shown. The reasoning status passes through a second filter under the same policy.
- `generate_titles` (ADR-0021 decision 9): on a session's first turn, after persisting the reply
  and before yielding `TurnCompleted`, the engine generates a switcher title and persists it, after
  the reply's own stream closed so the GPU lease is taken again rather than held twice. An
  `InferenceError` is absorbed and an empty title is not persisted.
- `progress` (a `ProgressSink`, ADR-0010 decision 13) is stamped onto each dispatch so a spawned
  subagent's steps reach the overlay while the turn's generator is suspended inside the spawn
  dispatch. The turn also holds its waits on it: `thinking` around each model stream, `calling`
  around each dispatch that was not refused, `asking` around a confirmation (ADR-0069 decision 9). `escalation` (an `EscalationSlot`, ADR-0030) is the turn's handoff slot, one per turn.
- `residency` (a `ResidencyQueue`, set only where a handoff can run): after storing the user
  message and before reading the history, a turn whose model another model's handoff keeps off the
  card holds `swapping` with `HANDOFF_AHEAD_DETAIL` until that scope ends, through
  `wait_out_handoff` (`handoff_wait.py`). The hold is announced, so the body's first gap ends
  there, and the history read afterwards includes what that handoff stored. A handoff that begins
  later is met at the lease instead: `HandoffAheadBackend(inner, queue, progress)` is an
  `InferenceBackend` that takes the same wait before each stream it passes to `inner`, with
  nothing awaited between its check and the lease, and closes the wrapped stream when it is
  closed. The orchestrator builds one per stream that can hand off (ADR-0069 decision 9).

`turn_output.py` is the half of the engine the deep model's phase shares word for word, so the two
cannot diverge (ADR-0030). `stream_turn_events(loop, channels, parts)` maps one tool loop's deltas
onto `TextDelta`, `StatusUpdate` and `ToolActivity`, accumulates reply text into `parts`, closes
the loop in a `finally` and flushes the channels on a clean end; `flush_channels(channels, parts)`
is that flush alone, for a caller that has to persist a partial reply after a failure.
`record_exchange(caps, taint, *, session_id, query, reply)` applies the tainted-memory policy both
phases share and **drops an opaque turn whatever `record_tainted_memory` says** (ADR-0029).

`cap_note` and `unreadable_call_note(stops, parts)` are the two sentences a turn can end with, read
off a `StopLedger` (`stops.py`, ADR-0048). `StopLedger.observe(stop)` takes one completion's
`DecodeStop` and `capped` reports whether any of them stopped at a token limit, any completion
counting rather than the last. `REPLY_CAPPED_NOTE` is streamed and appended to `parts` when one was
cut at a limit, and `UNREADABLE_CALL_NOTE` only when none was, so both callers can run them in
sequence and give the reader one explanation.

## The history one turn sends

- `HistoryWindow` (port, `windowing.py`) provides
  `async select(history, *, session_id, progress=None)`: what one turn sends to the model. It is
  async and takes the session because a window may consult the store or the model, and it takes the
  turn's `ProgressSink` so a window whose selection costs a model pass can say so (ADR-0038
  decisions 9 and 20). A window returns a subsequence of `history` in original order and may
  prepend derived context, but may never drop or alter a kept message.
- `CharBudgetHistoryWindow(max_chars)` is the shipped policy: the newest whole turns, grouped by
  consecutive `turn_id`, whose summed text fits `max_chars`, kept or dropped whole, stopping at the
  first overflow, with the newest turn always kept even when oversized. Characters stand in for
  tokens at about four per token, so the core needs no tokenizer, and `max_chars < 1` raises.
- `SummarizingHistoryWindow(inner, store, backend, model, clock, *, min_dropped_chars=0)`
  (`summarizing.py`, ADR-0038 decision 9) wraps a window so the turns it drops arrive as a
  model-written recap. Five properties define it. It only **adds**: the inner selection is returned
  untouched, and every failure path returns it exactly as the plain window would have, logged and
  never raised. It **caches** behind `SessionStore.set_recap`/`recap`, keyed by the boundary it
  covers, so an unmoved boundary costs nothing and a moved one folds the previous recap together
  with the newly dropped turns. It **releases the GPU** by going through `drain_text`. It is
  **fenced at both ends** (ADR-0038 decision 19): the prompt includes `SECURITY_PREAMBLE` and
  quotes the transcript inside `wrap_untrusted`, and the recap re-enters inside a fence. And it is
  **bounded** by `RECAP_BOUNDS`, a boundary move dropping fewer than `min_dropped_chars` new
  characters deferring the pass without moving `covers`. When it adds nothing it logs why with
  `capped` and `chars` (ADR-0038 decision 21).
- `recap_prompt.py` holds the text on both sides of that call: `build_recap_messages`,
  `fence_recap`, `RECAP_BOUNDS` (512 tokens, thinking off, trace budget zero), `collapse_recap(raw)`
  (the one-paragraph normalization every rule is written against), and `clean_recap(raw)`, which
  returns `""` for a reply with nothing in it, one that does not end a sentence, or one longer than
  `RECAP_MAX`. The last two are refusals rather than truncations, a cut account moving `covers`
  past turns its missing tail never reached.
- `HistoryRecap(text, covers)` (`sessions.py`) is that cached account, `covers` being how many
  messages from the start of the session it accounts for. It refuses a blank text or a `covers`
  below one.

## Session listings and titles

- `SessionSummary(session_id, title, preview, last_activity, hoisted=False)` (`sessions.py`,
  ADR-0021) is one recent chat as the overlay's switcher shows it, and `summarize_ends(session_id,
  first, last, *, title_override=None, hoisted=False)` derives one: `title` from the first message,
  `preview` from the last, each collapsed to one line and cut at `TITLE_MAX` (48) and `PREVIEW_MAX`
  (96) with an ellipsis. Taking only the two ends lets a store read two records rather than a
  history. A non-blank `title_override` replaces the derived title, and `summarize_session` is the
  whole-history form. `TITLE_MAX` is declared again in the overlay's `sessionState.ts`, and
  `scripts/crosscheck.py` compares the two.
- `merge_hoisted(summaries)` is the shared ordering rule: over an already deduplicated candidate
  set it stable-sorts by recency and then by `not hoisted`, so chats the user hoisted sort above the
  recency group, each group still most recently active first. It only reorders.
- `session_title.py` is brain-generated titling (ADR-0021 decision 9): `build_title_messages`
  builds the one-message prompt, `clean_title` collapses and cuts a reply to `TITLE_MAX` with a
  hard slice and no ellipsis, and `generate_title(backend, model, messages)` runs one tool-less
  completion and returns the cleaned title, keeping `TextChunk` only and letting `InferenceError`
  propagate. The request uses `TITLE_BOUNDS` (`max_tokens=TITLE_MAX_TOKENS` of 32, thinking off,
  trace budget zero); reaching that cap cannot change a stored title, while reaching it with
  thinking left on returns nothing (readings in [ranked-recall](../readings/ranked-recall.md)).

## The output guardrail

The laundering defence (ADR-0015): a URL that entered the turn through untrusted content must not
leave it in the reply.

- One URL's canonical identity is `normalize_url` (`url_identity.py`), nine passes in a fixed order
  that reduce a rewritten link to the same value as its plain twin: escape decoding to a bounded
  fixpoint, defang repair, format-character stripping, punycode decoding, NFKC folding, a curated
  cross-script confusable fold, an IDNA label separator fold that also closes a space-split host,
  the removal of what a parser deletes, and a special-scheme backslash fold (ADR-0058 decision 10).
  `extract_urls(text)` finds every clickable URL (`http(s)`, `ftp`, `mailto:`, `tel:`, and `data:`
  behind a media-type anchor so prose stays out) and normalizes it; the grammar, the separator
  forms, the confusable table and what a parser removes are in `urls.py`, `url_separators.py`,
  `url_confusables.py` and `url_removals.py`, and
  [ADR-0058](../adr/ADR-0058-url-recognition-and-identity.md) says what is left out. Both sides of
  the defence normalize, so a collected URL and its reappearance always compare equal.
- `held_from(buf) -> int` (`url_holdback.py`) is the streaming hold-back the filter's `feed` splits
  on: the index from which the buffer may still be growing a URL. Four forms are open and all four
  are bounded, and holding back is not redacting, so prose that never becomes a host is released
  whole and in order.
- `TaintView` (protocol) is the live taint signal the guardrail reads at scan time (`tainted`,
  `opaque`, `untrusted_urls`); the turn's `TaintLedger` satisfies it structurally, which lets the
  engine pass the live ledger while results keep arriving.
- `OutputGuardrail` provides `open(taint, *, allow) -> OutputFilter`: one turn's filter over that
  view and the URLs the user's own message contained. `OutputFilter` provides `feed(chunk)` (the
  scrubbed text safe to emit now, with an ambiguous suffix held back), `flush()` (end of stream
  resolves it), `policy` and `redactions()` (how many URLs it replaced under each ground, keyed
  `collected`, `lookalike` and `link`, zeros included, counted under the first ground that applies
  in the order collected, link, lookalike).
- A policy is a **set of grounds** rather than a mode (ADR-0015 decision 8). A URL is removed
  because its identity was `COLLECTED` from this turn's untrusted content, because it is a
  `LOOKALIKE` (a host that is not plain ASCII) on a tainted turn, or because it is a `LINK` at all
  on one. `UrlRedactingGuardrail` (the default) stands on `{COLLECTED}` and replaces a match with
  `REDACTED_LINK`, keeping trailing prose punctuation. `LookalikeUrlRedactingGuardrail` adds
  `LOOKALIKE`, reading the host from an identity built with the confusable fold switched off.
  `StrictUrlRedactingGuardrail` stands on `{LINK}`. An **opaque** turn adds `{LINK}` to whichever
  policy was configured (ADR-0029), a URL painted into pixels never being in the result text the
  default reads. The user's own allowlist answers before any ground. What each policy costs, in
  real hosts redacted, is in [output-guardrail](../readings/output-guardrail.md).
- `ThinkingChannel` and `open_output_channels(guardrail, taint, user_text)` (`output_channels.py`,
  ADR-0020 decision 6) extend the same defence over the thinking status, with one filter instance
  each so the two held buffers never mix. One turn's trace is one stream, so a URL split around a
  dispatch is joined before matching, and `release()` drains the scrubbed remainder once. With no
  guardrail both channels pass text through unchanged.
- `flush_channels` (`turn_output.py`) settles a reply: right after the reply filter's `flush` it
  reads `redactions()`, and when any count is above zero it logs `the output guardrail removed
  links from this reply` at `INFO` on `cortex_core.turn_output` with `collected`, `link`,
  `lookalike` and `policy`, never a URL and never a host.

**Invariants.**

- The assistant message is persisted if and only if `TurnCompleted` is emitted.
- The persisted reply equals the reply shown: the guardrail's output is what streams and what is
  stored.
- Nothing about a conversation outlives `handle_turn` except what `SessionStore` holds.
- A tainted turn is dropped from memory by default, or recorded with `tainted=True` and fenced on
  recall, so recall stays trustworthy either way.
