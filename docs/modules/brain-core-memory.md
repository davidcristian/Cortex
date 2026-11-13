# brain/packages/core: memory and recall

Part of [`cortex_core`](brain-core.md), which holds the shared values, the public surface rule and
the package invariants. This document covers durable memory: the embedder and store ports, the
recaller a turn calls, how a scope divides the namespace, and the policies that rank an over-fetched
pool down to the hits one turn sees. The turn that calls it is in
[brain-core-turn.md](brain-core-turn.md), and the pgvector adapter is in
[brain-memory.md](brain-memory.md). The decisions are ADR-0008, ADR-0019 and ADR-0038.

## Ports and values

- `Embedder` provides `async embed(text) -> Sequence[float]`: one stateless call, text to vector,
  whose dimension is fixed by the deployment's model and assumed nowhere here. Fake:
  `HashEmbedder(dimension=16, *, max_chars=EMBED_INPUT_CHARS)`, deterministic and I/O free, never
  returning an all-zero vector, and raising `EmbedderError` on a text over `max_chars`.
- `embedding_input(text)` (`embed_input.py`) returns the first `EMBED_INPUT_CHARS` characters of a
  text, which is 1800, or all of a shorter one. `EMBEDDER_CONTEXT_TOKENS` is 2048, the input bound
  of the shipped embedder; the model's tokenizer measured at most one token per character
  ([embedding-input.md](../readings/embedding-input.md)), so 1800 characters always fit.
- `MemoryStore` provides `add(record, *, recalled=()) -> bool`, `search(embedding, *, k, scopes=None)` (most similar
  first), `count_candidates(*, scopes=None)` and `delete_scope(scope) -> int`. `scopes` restricts
  the candidate set to those namespaces (ADR-0008 decision 9) and `None` ranks over every memory.
  `count_candidates` reports how wide that candidate set is, which `search` structurally cannot
  (ADR-0038 decision 14); it must be the store's own count and never a length over returned rows.
  `delete_scope` removes every memory in one namespace and returns how many, taking one required
  scope and no wildcard. `delete_tainted(*, scopes=None) -> int` removes every memory marked tainted
  in those namespaces, or in all of them, and `count_tainted(*, scopes=None) -> int` counts them.
  `delete_ids(ids) -> int` removes the listed rows in any scope and counts them; an id not stored
  adds nothing, and `find_text(text, *, limit, scopes=None)` returns the rows whose text contains
  `text`, case ignored, oldest first, and `find_value` the same with ` ./-` removed (ADR-0075). `delete_written_by(session_id) -> int` removes and
  counts every row that session wrote, in any scope (ADR-0021 decision 11). `add` stores the record only while every memory id in
  `recalled` still exists and returns whether it did, so a reply that recalled a memory a forget
  removed is not stored again. Fake: `InMemoryMemoryStore`; adapter: `cortex_memory`.
- `MemoryRecord(id, text, embedding, at, scope=GLOBAL_SCOPE, tainted=False, session_id=None)` is
  one durable memory and rejects a naive `at`; `MemoryRecaller.record` sets `session_id` to the
  writing session, and `None` marks a row stored before that was kept. `ScoredMemory(record, score)` is a retrieval hit and the store's **raw
  cosine similarity**, never the key a policy ranked by, so no caller can infer an order from it.
- `MemoryRecaller(store, embedder, clock, *, scope=GLOBAL_MEMORY_SCOPE, policy=RAW_RECALL_POLICY,
  id_factory=<uuid4>)` is the use case (ADR-0008). `record(text, *, session_id, tainted=False,
  recalled=())` embeds `embedding_input(text)`, persists the whole text and returns a
  `MemoryRecord`, or `None` when a memory in `recalled` is gone. `discard(memory)` deletes one
  record `record` returned, which `record_exchange` does when the chat was deleted meanwhile, under
  the write's bound. A `SessionStoreError` from that `deleted` read, or a failed or overrun
  `discard`, keeps the row and logs `the memory row of a chat that may be deleted was not removed`
  at `error` with `session_id` and `memory_id`; the turn completes. `recalls_across_chats` is true
  when a memory one chat writes can be recalled in another: under the global scope, and not under
  `SessionMemoryScope`.
  `recall(query, *, k, session_id, turn_id)` embeds `embedding_input(query)`, fetches `policy.candidate_k(k)` hits within `policy.read_scopes(session_id)` and
  awaits `policy.select(...)`, returning that ranking's memories cut to `k`; an empty ranking is no
  hits and is never refilled from the pool. An optional `audit: RecallAuditSink` gets one
  `RecallAudit` per recall, built inside an `is not None` check so an unaudited recall issues no
  counting query. The **id factory has a width past which the audit line stops holding whole
  candidates, and that width is 60 characters** (ADR-0051 decision 15);
  `brain/packages/orchestrator/tests/test_widest_line.py` fails the day a factory here crosses it.
- `MemoryScope` (port, `scope.py`) maps a turn's `session_id` to its `write_scope` and
  `read_scopes`. `GlobalMemoryScope` (the default) writes `GLOBAL_SCOPE` and reads everything;
  `SessionMemoryScope` writes and reads the session id. Selected through `CORTEX_MEMORY_SCOPE`.
- `SessionMemoryCascade(store, scope)` (`memory_cascade.py`, ADR-0021 decision 11) is the forget
  behind a session delete, kept out of the recaller and out of every engine, so no tool reaches it.
  It exposes only `delete_session_memories(session_id) -> int`, which removes every memory the
  session wrote (`delete_written_by`) and then, when the write scope is the session's own private
  space and not `GLOBAL_SCOPE`, that scope.
- `finish_cleanup(store, cascade, schedules, session_id)` (`chat_cleanup.py`, ADR-0021 decision 11)
  runs a deleted chat's cascade, then `detach_session`, then `SessionStore.clear_cleanup`, so a
  failed step leaves the chat in `pending_cleanups`. `CleanupRepeater` runs it for every pending chat
  in a task started by `start()`, at once and then every `CLEANUP_REPEAT_INTERVAL_S` (60 s), logging
  each failure; a failed read of the pending set is logged and read again on the next pass.
- `UntrustedMemoryForget(store, scope)` (`memory_forget.py`, ADR-0019 decision 9) is a delete
  a tool reaches: `forget(session_id)` calls `delete_tainted` over the session's read scopes. The
  built-in `ForgetUntrustedTool` over it is `forget_untrusted_memories`: no arguments,
  `confirm_required`, and a `RecordCard` whose card is the fixed `FORGET_CARD`, so the dispatcher
  shows it on a tainted turn too. A store failure returns an `is_error` result and forgets nothing.
  It is a `ToolOffer`: `offered(session_id)` is `any_to_forget(session_id)`, a `count_tainted` over
  the same read scopes, so a chat with nothing to forget is not offered it; a failed count offers it.
  `record_exchange` (`turn_output.py`) stores nothing for a tainted turn in which it ran `ok`.
- `ForgetChosenTool(store, scope)` (`memory_forget_chosen.py`, its result texts in `forget_results.py`, ADR-0075) is `forget_memories`: one
  `text` argument, `confirm_required`, and a `RecordCard`. `card` runs `find_text` over the
  session's read scopes and lists an excerpt of each match, so the card holds stored text and never
  the model's. It also lists, under a line naming the value, each other row holding a whole value
  of a match (`whole_values` in `memory_values.py`: a phone number or code in full, never a part,
  a year, a date, a time or an amount) and a word of four or more letters from the text, since a
  recall reply restates the value in other words; a text holding a value lists each row
  holding that value whole, with no literal match needed, except a row writing it only in groups of two digits at most (`12/25` for `1225`) and naming no code (`short_groups`). A match where a letter or digit touches the text at an end whose word holds a digit (`inside` in `forget_inside.py`: `015 123 456 789` inside `015 123 456 7890`, never `4242` at the end of a card), or, given a message, held only as groups of a longer whole value (`value_spans` in `memory_values.py`) other than its last group alone, in a message naming neither that value nor a card, an account or an IBAN, a kind word listing no row that only a remark outside the part asking to forget names (`0075` in `1B31 0075 9384 0000` for `Forget the code 0075.`), or as that last group when another match, or a row a call of the turn deleted, holds the text whole and the message names no word only this row has and asks for every row (`quantifies`) only beside a code word, unless it is the newest row the calling chat stored, no newer row of that chat was deleted by a call of the turn and the message names no word of any match or deleted row and no code word (`code_word`) (`4242` in a card for `Forget my gym code.` beside a gym code row, never for `Forget every 4242.`), where the words and the card, account or IBAN word are read only from the message less its remarks (`asking` in `forget_clauses.py`: each clause, or its words from a relative word after the value, holding no forget verb, keep clause or the value) when that part names a row holding the text whole or as a group, and a last group alone that a word of the message names and no word of that part names is kept (a phone `0721 555 4242` for `Forget the locker code 4242 that I texted from my phone.` or `Forget the card 4242, the one I read from my phone.`), or as that last group when the message does not hold the text and names a word, no function word of a language it is read in (`readings`) and none of this row's, with the same exception (`4242` in a card stored alone for `Forget my gym code.`, never for `Forget my Visa ending 4242.`), is kept and listed under `INSIDE_LINE`; a match holding the text only inside longer values (`_in_longer`) is kept under `KEPT_LINE` when a word or kind word of the message names another match and none names it, unless the message asks for every row (`_unnamed_groups`, read by `kept_rows`: a mobile phone `0721 555 4242` for `Forget the card ending in 4242.`), and so is any match of a text holding no digit (a bike lock code for `Forget my gym code.` with the text `code`), and a match a word after a word for minus in a clause names (`_after_minus`, over the minus words `MINUS` of `forget_kinds.py`: a card for `Uită codul 4242 mai puțin cel de pe card.`); beside such a row, a match holding the text whole is kept under `KEPT_LINE` when the message holds the text beside words naming no match (`kept_rows`, which also reads the unnamed rows below beside the rows kept this way), unless it also holds the text's value whole in other separators (`44 17` beside `44170` for `4417`), which lists it under "Listed because they also hold", and is in `ToolResult.spared`; when every match is such a row, the card is `None` and the result `INSIDE_ALL`, with `matched_nothing` unset. A match the unnamed reader below does not keep is also kept when the text names a value the message (`TurnStamp.query`) lacks and the match holds every value the message names only inside a longer value (`longer` in `forget_longer.py`); it is listed under `LONGER_LINE` and is in `ToolResult.spared` but never `ToolResult.inside`, a call whose every match is kept so (none unnamed) returns `LONGER_ALL` with no card, and a delete beside such rows returns `beside`. Every result has `ToolResult.inside`, the excerpts of the rows a call with no card kept this way that no later call deleted or kept as unnamed (`KeptRows.ids`). When the text holds a value the person's message lacks (`TurnStamp.query`), a match whose request holds that value and which holds no word of the message (three or more letters, no common word of English or of a language the message is read in, which is the one `message_language` picks and each whose forget verb, such as `VERGISS`, it uses (`readings` in `forget_languages.py`), a row any of those readings keeps being kept, no code word, read in a row without its `User:` and `Assistant:` labels, where the part of a compound code word before its code word, `code_stem` in `memory_values.py`, names only the same whole word or a row's same compound, so `Fahrradcode` names a `Fahrradcode` row and no `Fahrradschloss` row, and a compound naming no row keeps every row) is listed apart under `KEPT_LINE` and kept (`unnamed` in `forget_unnamed.py`); a call with no message reads no row apart; when the message holds the value too, those rows are kept only once a word of it names another match or a row the turn deleted, and no word such as `everywhere` or `all` stands within two words of a value, outside a clause asking to keep and not before `about` or `else`; a word of a clause asking to keep (`_split`: a keep verb form not negated, never a noun such as `guardian` or `keepsake`, a word for except (`except`, `excluding`, `sauf`, `außer`, `excepto`, never one that can mean minus such as `moins` or `menos`), `but` right after a word for all (`everything but`, `all but`), or a negation opening the clause or after `but`, `do` or `is` that no naming word such as `the` or `my` precedes, so `my do not disturb PIN` names a fact, until a forget verb not negated) names no fact to forget; beside such a clause a match is deleted only when a whole word outside it names the match (a code word for one kind of value, `kind_word` such as `PIN`, only when no other word names one) and no word of the clause does, in any language, so a misread keeps the row, or, when no word outside it names a match and each content word of the clause names one, a whole value outside it is the match's whole value (`_whole`); the clauses are read by `parts` in `forget_clauses.py`; a word of the closed card and phone table of `forget_kinds.py` (`carte`, `Karte`, `Telefon`) names a row holding a word of the same kind wherever these readers compare the message's words with a row's, except to list a row by a word of a clause holding a negation or a word for minus (`read_kinds`, the words and compound stems of every other clause); when no word of the message names a match or a row the turn deleted, a message with no word included, the newest match the calling chat stored (`MemoryRecord.session_id` and `at`) is not kept unless a row of that chat a call of the turn deleted is newer (`just_said`, over the deleted rows the tool keeps whole per turn id, which the deep model's calls after a handoff share), so a request to forget what was just said deletes it; a card whose rows are all kept is `None` with the result `KEPT_ALL`. Every result has `ToolResult.kept`, the excerpts of the rows a `KEPT_ALL` call of the turn kept that no later call deleted (`KeptRows`). It also has `ToolResult.spared`, the excerpts of every row a call of the turn kept, on a card or not, that no later call deleted; `names_spared` (`memory_claim.py`) reads them, so a reply whose only keep claim is that it kept such a row gets no `UNKEPT_CLAIM_NOTE`. Those rows are found by `find_value` with the value's letters
  and digits (`joined` in `memory_values.py`), so a row writing it in any groups is listed and the
  whole value filter drops a longer value. When those rows would pass
  `FORGET_CHOSEN_LIMIT` (20), the card lists the text matches alone and says the others stay, and
  the result says the value is not forgotten. It keeps the listed ids under the call's id (the
  latest 32 calls). `invoke` deletes exactly those ids with `delete_ids`, searches again, and says
  how many were removed and whether any match is left. When none is, it searches the remaining
  rows, by `find_value`, for each run of four or more digits a row deleted in the turn held (`code_runs` in
  `memory_values.py`, compared by digits alone: a year or a date only from a row naming a code or
  a number, such as `code`, `PIN`, `Nummer`, `código` or `codul`), leaving out a row that `asks_to_keep` (`forget_unnamed.py`) reads a keep clause of the message naming, or every row when that clause holds a word for all or the rest, and a row holding the run only as groups of two digits in a text naming no code (`undated_runs`), and when a row holds one the result says how
  many do and that a forget of the number itself would remove them, without naming it (after rows kept apart, only that they were kept and, for a text holding a digit, that the value is still remembered), and sets
  `ToolResult.numbers_left`. No text, no match, more than 20 rows
  containing the text or a failed store deletes nothing (a store that fails after `delete_ids` returns an error result saying how many rows were deleted, with `ToolResult.forgot` set): `card` returns `None`, so the dispatcher shows no card and runs the call,
  whose result says why. The description asks for the value or one word from the request that names
  it, and the no-match result tells the model to say that no remembered exchange contains that
  exact text and not to ask the user for the value. After a delete earlier in the same turn (the latest 32 turn ids that
  ran one are kept, with the deleted rows and the texts that deleted them), a no-match result whose
  text a deleted row contains, which contains an earlier text, or which holds a whole value of a
  deleted row says instead that the earlier call deleted it and that the reply must not say it was
  not stored or could not be found. It is a
  `ResultNote`: the dispatcher ends every result a call to it gets, run, declined, expired or
  refused other than as `UNASKED` or `FORGET_UNREQUESTED`, with `FORGET_NOT_KEPT_NOTE`, which says the message is not kept and asks the model to
  have the user send anything else in it again. `record_exchange` stores nothing for a turn that
  called `forget_memories`, whatever its result, since the query or reply may name the text; a deep
  phase passes the cortex's runs of the turn as `earlier`, so a forget before a handoff counts. A
  call that never ran counts too: the tool loop sets `TaintLedger.forget_asked` for every call the
  model names before any refusal or cut, except on a message `unasked_forget` or `forget_unrequested` reads, the engine and the deep phase set it for an unreadable call
  whose `MalformedToolCallError.tool_name` is the forget, and the handoff record keeps it for the
  deep phase. Each of those also counts in `TaintLedger.forget_calls` (`name_forget`), and the
  round counts a run whose result has `matched_nothing` set, which only the no-match run of
  `forget_memories` sets, in `forget_unmatched`.
- `memory_withheld(caps, taint, runs, *, query)` (`memory_claim.py`, ADR-0019 decision 10) is the
  one check of whether memory is on and stores nothing of a turn: an opaque turn whatever
  `record_tainted_memory` says (ADR-0029), a tainted turn whose `forget_untrusted_memories` ran
  `ok`, a turn that named `forget_memories` unless every call ran and matched nothing and
  `asks_kept(query)` reads a request to remember (ADR-0075 decision 5), a turn whose `query` `asks_not_kept`
  (`memory_request.py`, ADR-0075 decision 5) reads as a request not to keep, to forget or to
  remove something, with or without a call, a tainted turn under `skip`, and an untainted turn
  whose `query` `asks_files`. The `asks_not_kept` rule in one
  sentence: a clause that opens (also after a spaced hyphen, an en or em dash or an opening bracket), or follows "I mean", "I meant to say" or "what I mean is", with "don't", "never", "no need to", "remember not
  to" or "remember to not" before a keep verb, a keep verb or "put" before "nowhere" or "to nowhere" (not "nowhere near"), with "forget", "erase", "unlearn", "drop it", "get rid of" or "stop
  remembering", with "you should forget" (or "must", "need to", "have to") before the message, or
  that says "from your memory" or "off the record", asks not to keep; "remember not to", "remember
  to not", "get rid of" and "stop remembering" count only before the message ("it", "this", "my" and the like), as
  does any form after a request to remember in the same sentence; in French, German, Spanish and
  Romanian a negative imperative of a keep verb, or an imperative to forget or erase
  (`oublie`, `vergiss`, `olvida`, `uită`, not `vergiss es nicht`), at a clause start counts, and
  English `keep me waiting` and a `keep it to yourself` that ends its clause or asks to share do not
  (`or anyone` after it does); an idiom word after the keep verb
  (`rancune`, `rencor`, `răul`, `alles`, `contre`, `pour toi`, `für dich`, `para ti`), at most
  one word after it, keeps the turn, so `ne garde pas rancune` and `behalt das nicht
  für dich` do not count and `ne retiens pas cette information` and `n'enregistre pas ça` do. A save decision put off in the first person (`I'll tell you later whether to save it`, `let me decide if you should keep it`) asks not to keep too, in all five languages (`ich sage dir später, ob du es speichern sollst`), and `I'll tell you later what to do` does not.
  `asks_kept` reads English (`keep in mind` also with `it`, `this`, `that` or `these` between, not before `for him`, `for her` or `for them`) and, in those four languages, an imperative to remember at a
  clause start (`souviens-toi`, `retiens-le`, `merk dir`, `merk ihn dir`, `recuerda que`, `recuérdalo`, `ține minte`), and not a statement, a question, a
  reminder (`rappelle-moi`) or a request not to keep; `asks_kept_other` reads that imperative alone, and `asks_kept_fact_other` reads it only when it opens the message after any thanks, `que`, `dass` or `că` follows it, or a comma or colon and one statement of a fact in `STATEMENT_OTHER` (`fact_statement.py`: a possessive, at most six words, a copula and a value of at most four words) do, no second clause or sentence follows the fact, and the fact holds no obligation of the assistant (`tu dois`, `il faut`, `debes`, `hay que`, `trebuie`, `să`, `sollst`, `musst`) or second `que tu`, which ask for an action. `asks_files`
  (`file_request.py`) reads a sentence naming files, folders, directories or a file name such as
  `notes.txt` beside a question mark or a request word ("list", "show", "tell", "read", "which",
  "what" and the like), on a message `asks_kept` does not read as a request to remember; an
  untainted turn read no file tool output, so its reply names folders the cortex wrote itself.
  `record_exchange`
  returns on it, and `limit_notes` (`closing_notes.py`) reads it over the same runs and appends
  `UNKEPT_CLAIM_NOTE` when `unkept_note_due(query, reply)` holds: `asks_kept(query)` reads a request to
  remember and `asks_not_kept(query)` does not, or `asks_kept` reads one clause of a statement of the message, not a question, that `asks_not_kept` does not (a clause ends at a comma, a semicolon or a joining word such as `and` or `und`, and a request with no object, `Remember,`, is read with the next clause), whatever the reply says, since "I've updated that"
  is also what a reply says after a file edit. On a turn with a `forget_memories` call it also holds when `claims_updated(reply)` (`memory_claim_update.py`) reads a clause, not a question and with no `not`, `never`, `nothing` or `n't`, saying "I've updated", "changed", "corrected" or "replaced", or "has been updated", or a first line opening with "Updated". It also holds when `claims_kept_other(reply)` (`memory_claim_other.py`) reads such a claim in French, German, Spanish or Romanian outside a question, a condition and a negated clause, unless each such claim keeps or saves only words and numbers of a row still stored (`names_spared_other`, through `keeps_held`; `names_spared` reads an English one the same way) in `TaintLedger.forget_spared`, which holds the rows the turn's forget kept and those the message's keep clause names (`keep_named`, `forget_keep_named.py`), or when `claims_kept(reply)` finds a statement, not a question, saying something
  was noted, remembered, made a note of, or kept or saved "in mind" or "in memory" (each also after
  "I'll make sure to", and remembering after "I'll make sure I" or "I'll be sure to"), or that "my
  records" or "your information" were updated, or "your phone number" updated to a value, alone or
  after an earlier verb of "I" ("I read your lease and noted the address"). A bare "saved" or
  "stored" counts only after such a verb and with no place named, since a file tool's reply says it
  saved a file, and an update of a reminder or a file name does not count. Neither do the forms
  that point at text rather than memory: "as I noted", "noted above", "I will note that" before a
  clause that is not about "you", "has been noted by" or "that", a file name such as `memory.txt`,
  and a bare "Noted" past the reply's first line, which is a line read back from a file. With
  memory off the check is false and no note shows. A turn that ran out of rounds (`StopLedger.out_of_rounds`) on a statement holding a value of four digits or more (`states_value`, `memory_claim.py`) also shows the note, since its reply is the round cap note alone.
- `claims_chat_only(reply)` (`chat_only_claim.py`) is true when a statement, not a question, says
  something is kept, remembered or noted "for", "during", "in", "while" or "until the end of" this
  or our chat, conversation or session, and names no later or future one and no "not just"; in
  French, German, Spanish and Romanian a keep verb and a chat phrase ("mientras dure esta
  conversación") count in either order, and "pour le chat" (the cat) does not. On a turn memory stores under a scope that `recalls_across_chats`, `limit_notes`
  then appends `KEPT_BEYOND_CHAT_NOTE`, since every later chat recalls the exchange
  ([readings](../readings/remember-request-tool-search.md)); under `SessionMemoryScope` none shows. The note also shows when `claims_unsaved(reply)` (`unsaved_claim.py`) reads a clause of a statement saying the fact was not saved, stored, kept or noted ("I haven't saved it", "it was not stored", `n'a pas été enregistré`, `nicht gespeichert`, `no lo he guardado`, `nu l-am salvat`), unless the clause names a file, a folder, a change or a reminder. Its safe direction is that the note shows, and the note is true on every turn it reaches.
- `unread_folders_claim(taint, query, reply)` (`file_claim.py`) is true on an untainted turn whose
  `query` `asks_files` when `claims_folders(reply, query=query)` finds a statement with no condition
  ("if", "once", "such as") that says "I can read" or "access", "I have access" or "I am allowed to",
  beside a path, or above a list of folders or of paths, that `query` does not hold. A code fence and a
  code span holding a space are left out. `limit_notes` then appends `UNREAD_FOLDERS_NOTE`, with
  memory on or off and on a later turn too. `unread_folders_claim_other` (`file_claim_other.py`)
  reads the question and the claim in French, German, Spanish and Romanian.
- `unsearched_files_claim(taint, reply)` (`access_claim.py`) is true when the turn refused a
  `sidecar` or `calls_sidecar` call as `UNASKED` (`TaintLedger.sidecar_refused`) and a sentence of
  the reply, not a question and with no "if", "once", "when", "whether" or "until" before the
  match, says it has no access (`claims_no_access`: "don't have access", "can't access", "unable to
  access", "no access", "inaccessible") or did not see, find or locate something
  (`claims_not_found`: "don't see", "couldn't find", "can't locate", unless the next words name no
  object, as "why", "how" or "a reason" do), or `access_claim_other.py` reads either claim in
  the four other languages. `limit_notes` then appends `UNSEARCHED_FILES_NOTE`: no file was searched
  ([readings](../readings/no-access-after-a-refused-file-call.md)).
- `unforgotten_claim(runs, reply, *, unmatched=0)` (`forget_claim.py`, ADR-0075) is true when
  `claims_forgotten(reply)` finds a statement, not a question, saying something was forgotten, or
  removed, deleted, erased, wiped or cleared from memory or "my records", alone or after an earlier
  verb of "I" ("I've noted your code and have forgotten the old one"), no longer in memory or no
  longer remembered, or that memory was updated not to keep it, and no forget call in `runs` deleted a
  memory: no `forget_untrusted_memories` run is `ok`, and the `ok` runs of `forget_memories`
  number no more than `unmatched`, the turn's `forget_unmatched`. A clause whose subject is
  negated ("Nothing was removed") and a removal that names no memory ("I've removed the reminder")
  do not count. `claims_forgotten_other` (`forget_claim_other.py`) reads the same claims in French, German, Spanish and Romanian (`j'ai oublié`, `ich habe [...] vergessen`, `he olvidado`, `am uitat`, and a deletion beside a word for memory, and the French present `j'oublie`, `je l'oublie`, or `je supprime` beside memory, outside a habit word such as `souvent` and never after `que`), outside a question, a condition, a negated clause and a forgetting to do something. `limit_notes` reads `forget_unmatched` from the ledger and appends
  `UNFORGOTTEN_CLAIM_NOTE`, telling the person nothing was forgotten and to ask again in a
  message of its own, or `HANDED_CLAIM_NOTE` (`unforgotten_note`), which says nothing was forgotten before the handoff and asks for nothing, on a reply whose own approved `escalate_to_brain` run hands the turn to the deep model. The reply is every round's text and a denied card's run is not `ok`, so a
  claim a round streams before a card the person denies ends with the note too
  ([readings](../readings/forget-after-delete-provoked.md#a-claim-before-a-denied-card-the-draws-2026-11-07)). It also appends the note when `TaintLedger.forget_refused` says a call was
  refused as unasked and either `claims_kept` does not read the reply or `names_removal` does, which
  reads a statement naming a removal in any words with no negation in its clause. The handoff record keeps `forget_refused`, `forget_calls` and `forget_unmatched`, so a cortex
  forget that matched nothing before a handoff still counts as one in the deep phase.
  `run_round` sets `TaintLedger.forget_numbers_left` from each `forget_memories` result that
  deleted rows with no match left (`numbers_left` is `None` on every other result, a denied card
  included), and the count covers every row the turn deleted, so only a later delete of the rows
  left clears it. The handoff record keeps it, and while it is set a later call naming a value the message lacks is refused once ([brain-core-tools.md](brain-core-tools.md)). It also sets `TaintLedger.forget_kept` from each result's `kept`, which the handoff record keeps, and `limit_notes` appends `kept_note` (`forget_unnamed.py`), naming those rows, whenever it is not empty, whatever the reply says; the note asks for nothing. It sets `TaintLedger.forget_inside` from each result's `inside` the same way, kept by the handoff record, and `limit_notes` then appends `inside_note` (`forget_inside.py`, in the language `message_language` picks, `INSIDE_NOTES`), naming those rows. It sets `TaintLedger.forget_longer` from each result's `longer` the same way, and `limit_notes` appends `longer_note` (`forget_longer.py`, `LONGER_NOTES`) after `inside_note`, naming the rows kept for holding the message's value only inside a longer value. `limit_notes` then appends `NUMBERS_LEFT_NOTE` when `says_forgotten` (`numbers_left_claim.py`:
  `claims_forgotten`, `names_removal`, or a past participle of forgetting or deleting in French,
  German, Spanish or Romanian with no negation in its clause) reads the reply and `names_still_held`
  (English `still` before a verb such as `holds`, `stored`, `mentions` or `appears in`, in a
  clause with no condition such as `if` or `should` and no negation before it, and no negation
  after it, or a clause in any of the five languages naming another memory, such as `un autre souvenir` or `eine andere Erinnerung`, with a verb of holding and a digit and no condition, negation or removal, the verb not opening a relative clause such as `that mention` or `qui contiennent`) does not. The note tells the person the number is still held and that a forget of the number
  itself removes it; it deletes nothing
  ([readings](../readings/forget-value-repeats.md#the-note-the-brain-appends-drawn-2026-11-07)). When a call of the turn deleted rows and another matched nothing, `limit_notes` appends `DELETED_UNFOUND_NOTE` (`forget_unfound_claim.py`) to a reply `says_not_stored` reads, since the later text may have named the deleted fact in other words; the note says so and is true when it named a fact never stored ([readings](../readings/forget-later-call-other-words.md#the-replay-draws-2026-11-08)). When the approved deletes of the turn removed rows (`ToolResult.forgot`, summed into `TaintLedger.forget_deleted`, which the handoff record keeps) and `says_forgotten` reads no removal in the reply, `limit_notes` appends `forgot_count_note` (`forget_count_note.py`), the count in the message's note language, unless `DELETED_UNFOUND_NOTE` is due, and `NUMBERS_LEFT_NOTE` then follows when rows still hold the number ([readings](../readings/forget-count-note.md)). When the person denies a `forget_memories` card (`TaintLedger.forget_declined`), `limit_notes` appends `DECLINED_FORGET_NOTE` in the message's note language, saying the rows the card listed are still stored, unless `names_still_held` reads the reply as saying so, because a reply after a denied card can call the kept fact never stored. When a call of the turn matched nothing and no forget removed a row, `limit_notes` appends `UNMATCHED_FORGET_NOTE` whatever the reply says: nothing was deleted, the call searched for an exact text no remembered exchange contains, and any exchange stating the fact in other words is still stored ([readings](../readings/forget-matched-nothing-note.md)), or `HANDED_UNMATCHED_NOTE` (`unmatched_note`), which says the same of the time before the handoff, on a reply that hands the turn to the deep model. When the reply says a value was updated or changed (`claims_changed` in `memory_old_value.py`: `claims_updated`, or its French, German, Spanish and Romanian forms) or that it was noted (`claims_kept` or `claims_kept_other`), no forget of the turn deleted a row, and the message names an old value (`corrected_values`: `X, not Y`, `from Y to X` after a verb of change such as `change` or `move`, since "from Berlin to Paris" alone names a route, `replace Y with`, `instead of Y`, `no longer Y`, `Y is wrong`, and `pas`, `nicht`, `no` or `nu` after a comma; the old value counts only when it is a number or a capitalized word that is not a common word, and never in a sentence ending in `?`, since the note calls a stored row outdated, so `Da, nu știu.` and `Is my code 4862, not 4826?` name none; a clock time such as `9:00` is read whole) that a row the chat can recall holds whole (`MemoryRecaller.find_value`, then `holds`) and does not itself name as old, the turn sets `TaintLedger.old_value` before `limit_notes`, which appends `old_value_note` in the message's note language: a remembered exchange still holds the value, a later chat can recall it, nothing was deleted, and the person can ask in a message of its own to forget it. A store that cannot be read gives no note ([readings](../readings/correction-keeps-old-value.md#the-old-value-note-rule-written-2026-11-11-before-it-was-built)). Whatever the reply says, when no forget of the turn deleted a row, a message that is one English statement of a fact holding no negation (`FACT_VALUE` in `fact_statement.py`, as in `My alarm code is now 5528.`) sets it to the value a row the chat can recall states, with the same possessive, for a fact whose every word the message names (`my number` for `My new number is 0721 555 019.`), when both values hold a digit and the message holds neither that value nor a part of it ([readings](../readings/forget-refused-statement-old-row.md)).
- `RecallPolicy` (port, `rerank.py`) turns an over-fetched pool into the final `k` hits:
  `candidate_k(k)` sizes the pool and `async select(hits, *, query, now, k, session_id=None,
  turn_id=None) -> Ranking` reranks and cuts it, returning at most `k` hits from the pool, none
  twice, and leaving the pool as it was given, the recaller reading it again for the dropped set.
  `core/tests/recall_policy_contract.py` checks that over all five policies (ADR-0068
  decision 10), and it is async so a policy may call the model.
- The five policies: `RawRecallPolicy` (`RAW_RECALL_POLICY`, top-`k` cosine, this port's own default
  argument), and in `rerank_policies.py` with their math in `rerank_math.py`,
  `RerankingRecallPolicy` (similarity blended with an exponential recency decay), `MmrRecallPolicy`
  (greedy maximal marginal relevance) and `RecencyMmrRecallPolicy` (that selection over the recency
  blend). `JudgeRecallPolicy(backend, model, *, pool_factor, fallback=RAW_RECALL_POLICY)`
  (`rerank_judge.py`) asks the resident model to order the pool, each note on one line after its age
  (`memory_age.py`, "(age unknown)" for a date after now, which a clock that ran ahead wrote, so it
  never reads as the newest), under a JSON-schema-constrained request using `rank_bounds(k)`
  (`max_tokens=24 + 8k`, thinking off, trace budget zero) and falls back on any failure; an
  **empty** order is the model declining the pool and returns an empty ranking on the `DEMUR` basis
  without the fallback (ADR-0038 decision 11). A similarity floor was calibrated and **declined**
  (ADR-0038 decision 12).
- `Ranking`, `RankedMemory` and `RankBasis` (`ranking.py`) are what `select` returns.
  `RankedMemory` pairs a kept hit with the `key` its policy ordered by, and `Ranking` adds the
  `basis` naming that quantity: `ECHO` (raw cosine), `EMBER` (recency blend), `SPREAD` (MMR over
  cosine), `SWEEP` (MMR over the blend), `VERDICT` (the model's placing) and `DEMUR`. `comparable`
  is `False` for the two MMR bases, and a `DEMUR` ranking with hits is refused at construction.
- `RecallAudit` (`ranking.py`) is what a `RecallAuditSink` records: `session_id`, `turn_id`,
  `query`, `pool_size`, `available`, `k`, `ranking`, `dropped`, `at`. It contains conversation
  text, so the sink decides what it keeps and the shipped `LoggingRecallSink` keeps none.
  `dropped_candidates(pool, ranking, *, limit=DROPPED_TRAIL_LIMIT)` derives what the rank did not
  keep, each `DroppedCandidate` an id and the store's raw score with no rank key and no text.
  `DROPPED_TRAIL_LIMIT` is 20, the shipped pool width, and `omitted` counts what it left out.
- `drain_text(backend, model, messages, *, schema=None, bounds=None, stops=None)` (`drain.py`) runs
  one completion to its end and closes the stream in a `finally`, so the adapter's lease block is
  left before the call returns rather than nesting the turn's own reply inside it. Used by
  `generate_title`, `JudgeRecallPolicy` and `SummarizingHistoryWindow`, all three passing `bounds`.
  It logs a warning when it throws away a trace the request asked against (ADR-0049).

**Invariants.**

- No text longer than `EMBED_INPUT_CHARS` reaches the `Embedder`, so an exchange of any length is
  recorded and a query of any length recalls; what is stored is always the whole text.
- A tainted turn is dropped from memory by default, or recorded with `tainted=True` and fenced on
  recall, so recall stays trustworthy either way.
- A retrieval hit reports the store's raw similarity and never the key a policy ranked by, so no
  caller can infer an order from it.
- An audit record holds memory ids and scores and never the text a rank declined.
