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
  restarts: `append(session_id, message)` (an equal message is not stored again, so an adapter may
  retry a write whose reply was lost), `history(session_id)` (append order, empty when
  unknown), `list_sessions(*, limit)` (most recently active first), `set_title(session_id, title)`
  (a display title `list_sessions` prefers over the first-message derivation, ADR-0021 decision 9),
  `delete(session_id)` (erases a chat, marks it deleted so no later write is stored, and records
  its cleanup as pending), `deleted(session_id)`, `pending_cleanups()`, `clear_cleanup(session_id)`,
  `set_hoisted(session_id, *, hoisted)` (ADR-0021 decision 12), and `set_recap` / `recap` for the
  history recap below. Fake: `InMemorySessionStore`; adapter: `cortex_session`.
- `InferenceBackend` provides `stream(model, messages, *, tools=(), schema=None, bounds=None) -> AsyncIterator[InferenceEvent]`:
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
capabilities=TurnCapabilities())` (`engine.py`) is pure orchestration over the ports. The logical
id `"cortex"` is overridden through `CORTEX_MODEL_CORTEX`, read by the composition root.

`handle_turn(session_id, text, *, turn_id)` is an async generator. It routes through `route_turn`,
builds the user `Message` from the clock and the id it was given, appends it to the store, refuses a
deleted chat with `SessionDeletedError` (ADR-0021 decision 11), runs the inference and tool loop
over that history, yields one `TextDelta` per streamed chunk, then persists the assistant `Message`
and yields one `TurnCompleted`. Closing the stream part way (`aclose()`) keeps the persisted user
message, does not persist the partial reply, and closes the abandoned backend stream. A backend
failure surfaces as `InferenceError` after the user message was persisted, except two that **end**
the turn: `MalformedToolCallError` (the fragment is the model's own tokens, ADR-0048) and
`ContextOverflowError` (the prompt is longer than the context, ADR-0014 decision 7). A refusal
before any output is first asked again without the oldest windowed turns, `shed_oldest_turns`
(`shedding.py`) dropping 4.7 characters for each token of its `excess`. Otherwise the path flushes
the channels, streams its note, logs a warning naming the session and turn, and persists once: the
cut call's note is the one the `StopLedger` picks, and the overflow's is `MESSAGE_OVERFLOW_NOTE`
when only the newest turn was left, else `CONTEXT_OVERFLOW_NOTE`, never followed by a cap note.

`TurnCapabilities(memory=None, tools=None, window=None, guardrail=None, record_tainted_memory=False,
generate_titles=False, progress=None, escalation=None, bounds=None, residency=None, zone=UTC_DISPLAY)`
(`turn_context.py`, with the context assembly `assemble_inference_messages`) is the frozen bundle of
everything optional about a turn. With the bare default the turn is plain streamed inference. The
reply stores its turn's `ToolOutcome`s as `runs`, replayed before it as calls with fixed texts
after the window, one saying a handoff's deep reply is not stored (`tool_replay.py`, ADR-0074).

- `memory` (a `MemoryRecaller`, ADR-0008): before inference the engine recalls the top
  `DEFAULT_RECALL_K` (5) memories for the user text within the turn's scope and prepends any hits as
  a `Role.SYSTEM` message that is never stored, each trusted hit after its age (`memory_age.py`).
  The hits share `RECALL_CHAR_BUDGET` (6000 characters) through `fit_recalled` (`recall_budget.py`),
  and one past its share is cut with a marker. A `tainted` memory is fenced on one line with the
  turn nonce, taints the turn (ADR-0019), names its own record id as the turn's source and gives the
  taint ledger its whole text. `RECALLED_RUNS_NOTE` (ADR-0074 decision 6) ends the trusted header,
  or, with no trusted hit, is the block's first line, above the fenced header. After the reply it
  records the exchange, with a `Tools run` line naming the turn's runs when it made any, unless the
  turn read untrusted content. **Memory that cannot be reached costs the turn its notes and not the
  turn** (ADR-0008 decision 12): only `EmbedderError` and `MemoryStoreError` are caught; a failed
  read logs a warning and one `StatusUpdate`, a failed write, or one past `memory_write_timeout_s`
  (`MEMORY_WRITE_TIMEOUT_S`, 10 s, so a frozen embedder cannot hold a finished turn), an error only.
- `record_tainted_memory` (ADR-0019) governs writing only: with it on, a tainted turn is stored
  with `tainted=True` instead of being dropped, and a stored tainted memory is fenced either way.
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
  message and before reading the history, a turn whose model another handoff keeps off the card
  holds an announced `swapping` wait (`wait_out_handoff`: `HANDOFF_AHEAD`, then `RESTORING_AHEAD`
  from that scope's swap back on) until the scope ends, so the body's first gap ends there and the
  history read next includes what it stored. A handoff that begins later is met at the lease:
  `HandoffAheadBackend(inner, queue, progress)` takes the same wait before each stream, awaiting
  nothing between its check and the lease, and closes the wrapped stream when closed (ADR-0069).
- `LoadWaitBackend(inner, progress, *, clock, sleeper, wait_s)` (`load_wait.py`) asks `inner` again
  every `LOAD_POLL_INTERVAL_S` while it raises `ModelLoadingError` before its first event, holding
  `MODEL_LOADING` (`swapping`) until that event, and re-raises `wait_s` after the first loading
  answer; calls inside one `turn()` share that bound, which `LoadWaitTurns` opens per turn. Other
  errors pass at once, and Stop or the drain ends the wait and its hold (ADR-0054 decision 10).

`turn_output.py` is the half of the engine the deep model's phase shares, so the two cannot diverge
(ADR-0030). `stream_turn_events(loop, channels, parts, stops, query)` maps a tool loop's deltas onto
`TextDelta`, `StatusUpdate` and `ToolActivity`, adds reply text to `parts`, ends the reply when
`RepeatWatch(query)` (`repeat_watch.py`, new at each tool call) sees a block of up to four lines, one of
20 or more characters not in `query`, come 3 times back to back, once more than a count `query` asks for,
or 13 times when it asks for copies with no count (ADR-0048 decision 17), closes the loop in a `finally` and flushes the channels on a clean end.
`record_exchange(caps, taint, *, store, session_id, query, reply, runs, earlier=())` stores nothing when
`memory_withheld` holds over `query`, `runs` and `earlier` (the cortex's runs before a handoff) or
`store.deleted` holds, read again after the write (ADR-0021 decision 11). `limit_notes(stops, runs,
parts, *, caps, taint, query, earlier=(), said=())` (`closing_notes.py`), `unreadable_call_note(stops, parts)` and
`overflow_note(parts, *, alone)` are the notes a turn can end with, the first two read off a `StopLedger`
(`stops.py`): `capped` (a token limit cut a completion, ADR-0048), `out_of_rounds` (the last round still
ended in calls, ADR-0009) and `repeated` (the watch ended the reply). `limit_notes` appends
`REPLY_CAPPED_NOTE`, `ROUNDS_SPENT_NOTE` naming each of `runs` with its outcome, `REPEATED_LINE_NOTE`,
`UNSCHEDULED_CLAIM_NOTE` when `unscheduled_claim` (`schedule_claim.py`) finds a claimed schedule with no
`SCHEDULING_TOOLS` run succeeding in `runs` or `earlier` (not a "scheduled" claim naming no reminder or
task that the person's messages, `said`, made first; a sentence naming a reminder or alarm that no word for a fact the person keeps (`code`, `PIN`, `password`, `number`, `preference`, `system`, `company`) follows, or opening with `it`, `this` or `that` after one that does, or holding `it`, `them` or `one` right after the update or move verb after one that does, with the person's last message read as the sentence before the reply's first, also claims with `moved` or with an update as `claims_updated` (`memory_claim_update.py`) reads one, so a cancel alone under `I've updated your reminder` gets the note and a memory update under `I've updated your alarm code` does not; a sentence naming a reminder or alarm the same way that says it `now` goes off, fires, rings or sounds, or `is now at` or `for`, beside a time of day, with no condition word (`if`, `unless`, `once`, `would`, `could`, `can`, `should`) and no negation before those words, also claims (`_fires_now`), so `Done, your 9:00 reminder now goes off at 9:30.` does and `Your reminder now fires at 9:30, not 9:00.` does too; `claims_scheduled_other` in `schedule_claim_other.py` reads the same claims in French, German, Spanish and Romanian), `MONTHLY_STORED_NOTE` when `TaintLedger.monthly_stored` (a `schedule_task` call stored `on_month_days`) and `claims_yearly` (the reply names a yearly repeat and no month) or `claims_yearly_other` (`schedule_yearly_other.py`, the same in French, German, Spanish or Romanian, outside a question, a condition or a negated clause, where French `mes` and Romanian `luni` name no month) hold, `STORED_TIME_NOTE` naming `TaintLedger.stored_time` (the `HH:MM` the last successful `schedule_task` call given `at` or `at_time`, or `edit_scheduled` call, stored, read by `stored_time` from the result's `due` time) when it is set and `names_time_of_day` finds no clock figure (`9:00`, `9 Uhr`, or an hour written with h, such as `à 17h30` or `à 18h`, only after a word for a point in time, and after `réglé pour` and the like only from 13 to 23 or before `du matin`, `du soir` or `de l'après-midi`), am or pm, noon or midnight in the reply, `DAILY_STORED_NOTE` (`schedule_daily.py`) when `TaintLedger.daily_stored` holds the id of an item a `schedule_task` call this turn stored or found repeating every day, or an `edit_scheduled` call gave `at_time` with no day selector, less one a later `edit_scheduled` with `every_seconds` or a day selector, or a `cancel_scheduled`, changed, and `names_repeat` finds no sentence of the reply that states a repeat in any of the five languages (`it will now repeat` counts before a clause end or a day or time word, and `it will repeat the question` does not; a question, a sentence holding a condition or an offer, and a negated clause do not count; a purpose clause such as `so you don't forget` or `pour que` and `like you asked` are read past, and an adjective such as `daily`, `täglich` or `zilnic` counts only within two words of a word for the reminder or for reminding, so `your daily vitamins` names none; a clause is read only up to a relative form or a later `you` and its verb, `_OWN_TEXT`, so `the pill you take every morning`, `que tu prends`, `que tomas`, `pe care` and `die du` name none), `MADE_REPEATING_NOTE` (`schedule_made_repeating.py`) under the same reply check when `TaintLedger.made_repeating` holds the id of an item a successful `edit_scheduled` call this turn gave `repeat` true, `at_time` and a day selector while its result's `was_once` said the item was one time before the call, which turns it into a rule on those days, less one a later `cancel_scheduled`, an `every_seconds` or an `at_time` with no day selector changed, `CANCELLED_NOTE` (`schedule_cancelled.py`) whatever the reply says when `TaintLedger.cancelled` holds the text of an item a successful `cancel_scheduled` call of the turn deleted and no `schedule_task`, `edit_scheduled` or `snooze_scheduled` call of the turn, `earlier` included, succeeded, naming each text on its own line cut to 80 characters (`run_round` adds `ToolResult.cancelled`, which the cancel reads before it deletes the item, naming an item it cannot read or that came from untrusted content by its id; the texts come across the handoff record, and the note reads no message, so it shows after a plain cancel too), `ONCE_STORED_NOTE` (`schedule_weekly.py`) whatever the reply says when `TaintLedger.once_after_weekly` holds (`run_round` sets it when `stores_once` reads a `schedule_task` call with no `at_time` and no nonzero `every_seconds` that ran after `LoopRecord.weekly_refused` held a call, in the deep phase too, where that list starts from the cortex's refused calls and the flag comes across the handoff record), `WEEKDAY_OFF_NOTE` (`schedule_weekday.py`, in the language `message_language` picks) naming the weekday and date, once for each distinct date of `TaintLedger.weekday_off`, whatever the reply says (`run_round` adds an item id and date pair to it when `weekday_off` reads a one-time `schedule_task` call, or an `edit_scheduled` call that moved an item with `at`, that ran with an ISO `at` one day before or after the one weekday `one_named_weekday` reads in the person's message, beside any repeat or change word, since a note's safe side is to show, the `at` read in `ToolLoopContext.zone`; `weekday_off_after` drops only the pair of an item a later successful call of the turn cancels, snoozes or edits with anything beside `text` and `repeat`, and on any such change a pair whose store's result named no id, so the note never names a date the store no longer holds; no call is refused for it, and the pairs come across the handoff record), `FIRST_FIRE_NOTE` (`schedule_first_fire.py`, in the language `message_language` picks, `FIRST_FIRE_NOTES`) naming a first fire's day word (`today`, `tomorrow` or `in N days` in that language, from the day count `day_word` reads), weekday, date and time, once for each distinct first fire of `TaintLedger.early_first_fire`, whatever the reply says (`run_round` adds an item id, first fire and day count triple when `early_first_fire` reads a successful `schedule_task` call with `at_time`, or `edit_scheduled` call setting `at_time` or a day selector, whose result's `due` time, read in `ToolLoopContext.zone`, is on a day before the one `days_named` reads in the person's message: 1 day for `tomorrow`, `demain`, `morgen`, `mañana` or `mâine`, less a morning such as `jeden Morgen` or `por la mañana`, 2 for the day after tomorrow, or the days to the one weekday `one_named_weekday` reads, where today's weekday names none; a later cancel, snooze or edit of that item other than of only `text`, `repeat` or `every_seconds` drops its triple, an edit adding its own when early, no call is refused for it, and the triples come across the handoff record), `WEEKLY_STORED_NOTE` (`schedule_weekly_stored.py`, English only) naming the weekdays of each distinct set in `TaintLedger.weekly_stored` unless a sentence of the reply states a repeat as `names_repeat` reads it with `daily` false, so `every day`, `jeden Tag` and the other every-day phrases name none, here also `every Wednesday`, `on Wednesdays`, `each week`, `once a week`, `jeden Mittwoch`, `mittwochs`, `jede Woche`, `chaque mercredi`, `tous les mercredis`, `cada miércoles`, `los miércoles`, `todas las semanas` and `în fiecare miercuri`, and `weekly`, `wöchentlich`, `hebdomadaire`, `semanal` or `săptămânal` beside a word for the reminder, while `am Mittwoch`, `mercredi`, `el miércoles` and `miercuri` alone name one day (`run_round` adds an item id and weekday names pair when `weekly_after` reads a successful `schedule_task` call with `at_time` and `on_days` short of every day, an edit of that item setting only `on_days` short of every day, beside `at_time`, `in_zone`, `text` or `repeat`, names its new weekdays, a cancel or another edit of it setting `at`, `at_time`, `every_seconds` or a day selector drops it, no call is refused for it, and the pairs come across the handoff record), `QUOTED_STORED_NOTE` (`schedule_quoted.py`, English only, shown before `WEEKDAY_OFF_NOTE`) naming the repeat (`TaintLedger.daily_stored`) and time (`TaintLedger.stored_time`) when a `schedule_task` call of the turn, `earlier` included, succeeded and `quoted_request_only` reads a word for reminding (`remind`, `rappel`, `erinner`, `recuérd`, `amint` and the like) inside quotation marks (`"`, `“”`, `„“`, `«»`, `»«`, an unclosed mark quoting to the end, and a straight mark after a digit, as in `27"`, read as an inch mark unless a letter follows it), at least one word outside them, and no word for reminding, waking or alerting outside them, whatever the reply says, `UNKEPT_CLAIM_NOTE` when `memory_withheld` and
`unkept_note_due` hold, `KEPT_BEYOND_CHAT_NOTE` when memory stores the turn under a scope that `recalls_across_chats` and `claims_chat_only` (`chat_only_claim.py`) reads the fact as kept for this chat only, then `UNFORGOTTEN_CLAIM_NOTE`, `NUMBERS_LEFT_NOTE` (`numbers_left_claim.py`) when `TaintLedger.forget_numbers_left` holds and the reply says something was forgotten without saying it is still held, `kept_note` (`forget_unnamed.py`) naming the rows in `TaintLedger.forget_kept`, `DELETED_UNFOUND_NOTE` (`forget_unfound_claim.py`) when a forget call of the turn deleted rows, `TaintLedger.forget_unmatched` counts a call that matched nothing and `says_not_stored` reads a statement that something was not found, stored or saved, or `says_not_stored_other` (`forget_unfound_other.py`) reads one in French, German, Spanish or Romanian: a negation beside a find or store verb in one clause, or a no-record form such as `aucune trace` or `keinen Eintrag`, while a question, a clause after a condition word, a clause naming a new fact and one saying the delete held (`plus`, `mehr`, `ya no`, `mai`) do not count (a question, a clause naming something `new`, as a fact of this message a forget did not keep is, and a clause saying no records of a fact remain or are left do not count, unless the sentence also says the person never told, gave or mentioned it), `UNMATCHED_FORGET_NOTE` (`forget_unfound_claim.py`) when `TaintLedger.forget_unmatched` counts a call that matched nothing and no forget of the turn removed a row or deleted a memory, whatever the reply says, `DECLINED_FORGET_NOTE` (`forget_unfound_claim.py`, in the message's note language) when `TaintLedger.forget_declined` holds, which a Deny on a `forget_memories` card sets and the handoff record keeps, and `names_still_held` does not read the reply as saying the rows are still held, `UNREAD_FOLDERS_NOTE` and `UNSEARCHED_FILES_NOTE`
([brain-core-memory.md](brain-core-memory.md)). `place_note` sets a note one blank line under text, or
with no break when there is no text, in a `NO_TEXT` form for an overflow or unreadable call note. Every note `limit_notes` appends is written in the language `message_language(query)` (`note_language.py`) picks from the person's message, and in English when it picks none, except `ROUNDS_SPENT_NOTE`, `QUOTED_STORED_NOTE` and `WEEKLY_STORED_NOTE`, which fill English tool names, phrases or weekday names into their text and are English only; a note with a mapping keeps it beside its English constant (`UNKEPT_CLAIM_NOTES` beside `UNKEPT_CLAIM_NOTE`) ([ADR-0076](../adr/ADR-0076-closing-note-language.md)); `stored_time_note` (`schedule_claim.py`) writes the Spanish `a la` before a time from 01:00 to 01:59 and `a las` before any other.

`SerialTurnRunner(inner, locks, progress=None)` (`session_turns.py`) is the `TurnRunner` every
`Converse` stream runs. A turn holds its session in the shared `SessionTurnLocks` from before it
stores its question until its reply is stored, so a second turn on that session, from any stream,
waits under the `queued` wait `CHAT_AHEAD`, whose close clears the chip, then reads the first's
reply. One cancelled while it waits stores nothing. A session's lock goes with its last turn.

## The history one turn sends

- `HistoryWindow` (port, `windowing.py`) provides `async select(history, *, session_id,
  progress=None)`: what one turn sends, a subsequence of `history` in order that may prepend
  derived context but never drops or alters a kept message. The session and the `ProgressSink`
  are there for a window that reads the store or costs a model pass (ADR-0038 decisions 9 and 20).
- `CharBudgetHistoryWindow(max_chars)` is the shipped policy: the newest whole turns, grouped by
  consecutive `turn_id`, whose summed text fits `max_chars`, stopping at the first overflow, the
  newest always kept; `max_chars < 1` raises. Characters stand in for tokens (ADR-0014 decision 3).
- `SummarizingHistoryWindow(inner, store, backend, model, clock, *, min_dropped_chars=0)`
  (`summarizing.py`, ADR-0038 decision 9) wraps a window so the turns it drops arrive as a
  model-written recap. Five properties define it. It only **adds**: every failure path returns the
  inner selection untouched, logged and never raised. It **caches** behind
  `SessionStore.set_recap`/`recap`, keyed by the boundary it covers, so an unmoved boundary costs
  nothing and a moved one folds the previous recap together with the newly dropped turns. It
  **releases the GPU** by going through `drain_text`. It is **fenced at both ends** (ADR-0038
  decision 19): the prompt includes `SECURITY_PREAMBLE` and quotes the transcript inside
  `wrap_untrusted`, and the recap re-enters inside a fence. And it is **bounded** by `RECAP_BOUNDS`
  and reads what `fold_slice` keeps, a boundary move dropping fewer than `min_dropped_chars` new
  characters deferring the pass without moving `covers`. A rejected account is logged with `capped`
  and `chars` (ADR-0038 decision 21) and stored as `unfolded_recap(previous)`, so `covers` moves on and the same fold is not sent again next turn.
- `recap_prompt.py` holds the text on both sides of that call: `build_recap_messages`, `fold_slice`
  (the oldest dropped messages within `RECAP_READ_MAX`, 16,000 characters, a first one past it kept
  as its first 12,000 and last 4,000 characters around a line naming the cut, `covers` moving only past the messages read), `fence_recap`,
  `RECAP_BOUNDS` (512 tokens, thinking off, trace budget zero), `collapse_recap(raw)` (the
  one-paragraph form every rule reads), and `clean_recap(raw)`, which returns `""` for an empty
  reply, one that does not end a sentence, or one longer than `RECAP_MAX`: a refusal rather than a
  cut, since a cut account would move `covers` past turns its missing tail never reached. `unfolded_recap(previous)` is the previous account followed once by `UNFOLDED_NOTE`, a line saying part of the conversation could not be summarized.
- `HistoryRecap(text, covers)` (`sessions.py`) is that cached account, `covers` being how many
  messages from the session's start it accounts for. It refuses a blank text or `covers` below one.

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

The laundering defence (ADR-0015): no URL from the turn's untrusted content may leave in the reply.

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
  `REDACTED_LINK`, keeping trailing prose punctuation and a closing markdown delimiter.
  `LookalikeUrlRedactingGuardrail` adds `LOOKALIKE`, reading the host from an identity built with
  the confusable fold switched off. `StrictUrlRedactingGuardrail` stands on `{LINK}`. An **opaque**
  turn adds `{LINK}` to whichever policy was configured (ADR-0029), a URL painted into pixels never
  being in the result text the default reads. The user's own allowlist answers before any ground.
  Each policy's cost, in real hosts redacted, is in [output-guardrail](../readings/output-guardrail.md).
- `ThinkingChannel` and `open_output_channels(guardrail, taint, user_text)` (`output_channels.py`,
  ADR-0020 decision 6) filter the thinking status the same way, one filter each, so the held buffers
  never mix. A turn's trace is one stream, so a URL split around a dispatch is joined before matching;
  `release()` drains the remainder once. The first reasoning after a tool step starts with a blank
  line (`ROUND_BREAK`) added after the filter. With no guardrail nothing else changes the text.
- `flush_channels` (`turn_output.py`) settles a reply: right after the reply filter's `flush` it
  reads `redactions()`, and when any count is above zero it logs `the output guardrail removed
  links from this reply` at `INFO` on `cortex_core.turn_output` with `collected`, `link`,
  `lookalike` and `policy`, never a URL and never a host.

**Invariants.**

- The assistant message is persisted if and only if `TurnCompleted` is emitted.
- The persisted reply equals the reply shown, the guardrail's output and the notes included.
- Nothing about a conversation outlives `handle_turn` except what `SessionStore` holds.
- A tainted turn is dropped from memory by default, or recorded with `tainted=True` and fenced on
  recall, so recall stays trustworthy either way.
