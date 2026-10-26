# Readings: long idle and expiry, through the brain and the overlay

What a person saw, what the brain logged and what was lost when a chat sat idle for hours, a
confirmation card was left unanswered past its timeout, the brain was frozen across a reply and a
reminder's due time, and a reminder months ahead outlived a restart of Redis and the brain. Read
with [ADR-0022](../adr/ADR-0022-email-write-confirmer.md) (the confirmation card),
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md) and
[ADR-0066](../adr/ADR-0066-reminder-toast-and-card.md) (reminders). Restarts of Redis and the brain
between turns are in [store-and-process-restarts.md](store-and-process-restarts.md), times around
the clock change in [schedule-time-edges.md](schedule-time-edges.md), a turn inside the tool rest
in [overlay-tool-failure-flows.md](overlay-tool-failure-flows.md); none is repeated here.

## The rig

**2026-10-26**, the `cortexn8` GPU stack at the tree of that night: the resident cortex
(gemma-4-12B) at a context of 16,384 tokens, the deep tier set up but stopped, the Redis schedule
backend in `Europe/Berlin`, memory on pgvector. Redis runs with `--appendonly yes` on its own
volume. Flows ran over `Converse` from a driver on the host that prints every event with its time,
and on the Linux shell ([body-overlay.md](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless))
on `Xvfb`, which has no notification service. SM clock at each flow's start: 0.60 of
`clocks.max.sm`.

## Every time bound in the brain

| Bound | Default | Setting | Set in |
| --- | --- | --- | --- |
| A chat's messages and the chat index | none | | `cortex_session/store.py` (no expiry is written) |
| A handoff record once it has ended | 3600 s | | `_TERMINAL_TTL_SECONDS`, `cortex_session/handoffs.py` |
| A handoff record in flight, and the active pointer | none | | `cortex_session/handoffs.py` |
| A delegated task and its result | 3600 s | | `_TASK_TTL_SECONDS`, `cortex_session/tasks.py` |
| A confirmation card | 120 s | `CORTEX_SEAM_CONFIRM_TIMEOUT_S` | `cortex_orchestrator/converse_stream.py` |
| A schedule claim's lease | 300 s | `CORTEX_SCHEDULE_LEASE_S` | `cortex_orchestrator/config_schedule.py` |
| The schedule poll | 5 s | `CORTEX_SCHEDULE_POLL_S` | same |
| A schedule item or a fired, undelivered reminder | none | | `cortex_session/schedules.py` |
| A repeat interval or a delay | 60 s to 315,360,000 s | | `MIN_EVERY_SECONDS`, `MAX_EVERY_SECONDS`, `cortex_core/schedule_args.py` |
| A one-time `at` | up to `datetime.max` | | `cortex_core/schedule_args.py` |
| A tool call | 60 s | `CORTEX_TOOLS_CALL_TIMEOUT_S` | `cortex_core/tool_deadline.py` |
| A tool listing | 10 s | `CORTEX_TOOLS_LIST_TIMEOUT_S` | same |
| The rest after an overrun | 120 s | `CORTEX_TOOLS_RETRY_AFTER_S` | same |
| Silence from llama-server inside a reply | 120 s | `CORTEX_INFERENCE_STALL_TIMEOUT_S` | `cortex_orchestrator/config.py` |
| A wait for a tier to load | 120 s | `CORTEX_INFERENCE_LOAD_WAIT_S` | same |
| The deep model's load in a swap | 300 s | `CORTEX_SWAP_LOAD_TIMEOUT_S` | `cortex_core/model_host.py` |
| The slow-handoff note | 3600 s | | `DEFAULT_SPILL_DWELL_S`, `cortex_core/residency_pace.py` |
| A subagent's admission wait and run | 7200 s, 2400 s | `CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` | `cortex_core/scheduler.py`, `cortex_core/subagents.py` |
| A body call, a capture | 5 s, 10 s | `CORTEX_BODY_CALL_TIMEOUT_S`, `CORTEX_BODY_CAPTURE_TIMEOUT_S` | `cortex_body_client/gateway.py` |
| A memory's recency weight | half life 30 days | `CORTEX_MEMORY_RECALL_HALF_LIFE_DAYS` | `cortex_orchestrator/config.py` |

On the body side, a turn's stream ends with `no reply within <bound>` when no event arrives within
the link's bound (`body/crates/core/src/link.rs`); that bound is 120 s in the flow below. Nothing a
person typed or was told has an expiry: `TTL` on a chat key and on `cortex:sessions` read `-1`.
The 3600 s records are read only inside the run that wrote them.

## A chat idle for hours, continued after both stores restarted

A chat whose only turn was at 01:02 was continued at 04:34 over `Converse`, after Redis
(`docker restart`, data kept) and then the brain had been restarted at 04:33 with nothing in
flight. Asked to quote the first thing said in the chat, the reply quoted it exactly
("Please remember this: my best friend is called Tomas.") in 7.6 s. Nothing was lost, and the brain
logged no error or warning.

## A confirmation card left unanswered past its timeout

"Please hand this to the deep model: give a careful proof that the square root of 2 is
irrational." over `Converse`, the driver holding the `escalate_to_brain` card for 130 s and then
sending an approval.

- The card came at 6.5 s. 120 s later the brain logged
  `confirmation timed out; denying tool=escalate_to_brain` and sent `confirm_resolved` with
  outcome `timeout`. The approval sent after that matched no waiting card; `RpcConfirmer.resolve`
  drops such an answer with a debug line only.
- The cortex then wrote the proof itself, in full, and said nothing about the deep model: the
  reply did not say the handoff had not happened or that the card had expired. The stored reply
  names the run as `escalate_to_brain` with `ok: false`.
- On the overlay the card closes on `confirm_resolved` and nothing else is drawn
  (`turnState.ts`), as ADR-0022 decides, on the premise that the model's reply explains the denial.
  Here it did not, so a person who comes back to the screen after two minutes sees a cortex answer
  to a request they asked the deep model to answer, with no sign that anything expired.

The rows below were run under a rule written first: five rows, the same request,
`CORTEX_SEAM_CONFIRM_TIMEOUT_S` at 8 s, the card never answered. A row passes when its reply says
the deep model was not asked or the handoff did not happen, in any words, and fails when it answers
the request itself without saying so. A null of 0 or 1 failure in 5 makes the first run rare; 3 or
more confirm it.

| Row | Card | Reply's first sentence | Result |
| --- | --- | --- | --- |
| 1 | `timeout` at 14.4 s | "The request to escalate this task to the deep model was declined because that action requires explicit user approval." | pass |
| 2 | `timeout` | "... the request to hand this task over to the "deep model" was declined because that process is reserved for extremely complex tasks ..." | pass |
| 3 | `timeout` | "I'm sorry, but I cannot hand this task over to the deep model at this time because that action requires your explicit approval." | pass |
| 4 | `timeout` | "I'm sorry, but I cannot hand this task over to the deep model because that action requires your explicit approval." | pass |
| 5 | `timeout` | "I cannot automatically hand this task over to the deep model because that process requires your explicit confirmation ..." | pass |

0 of 5 failed, so the first run's silence is rare (1 of 6 in all). Every row then wrote the proof itself. No reply
said the card had gone unanswered or expired: two said the request was declined, which the person
did not do, and the result text the model is given starts with `DECLINED:`
(`UNANSWERED_MSG`, `cortex_core/untrusted.py`). That observation was not in the rule, so it got a
rule of its own, below.

### What the reply says about an expired card

Rule, written before any row: ten rows of the request above, `CORTEX_SEAM_CONFIRM_TIMEOUT_S` at
8 s, the card never answered, a new chat per row. A row passes when its reply says the request was
not answered in time or expired, in any words, and does not say the person declined it. The
baseline is drawn on the tree first. A result text of its own for a timeout ships if it passes 8 or
more of 10 where the baseline passes 2 or fewer.

Each row's exchange is stored as a memory and later rows recall earlier ones, so the baseline's ten
memories were deleted before the candidate's rows. The SM clock read 0.59 to 0.60 of its maximum
(`clocks.sm` over `clocks.max.sm`) at the start of every baseline row.

| Row | Card | Reply's first sentence | Result |
| --- | --- | --- | --- |
| 1 | `timeout` | "Here is a careful proof that the square root of 2 ($\sqrt{2}$) is irrational." | fail |
| 2 | `timeout` | "I'm sorry, but I cannot directly hand tasks over to the "deep model" for you." | fail |
| 3 | `timeout` | "I'd be happy to escalate this request to the deep model ... However, ... I need your explicit permission to proceed." | fail |
| 4 | `timeout` | "The request to hand this task to the deep model was declined because it's an irreversible action that requires your explicit approval." | fail |
| 5 | none | "... it will prompt you for an explicit confirmation before it proceeds." | fail |
| 6 | `timeout` | the same sentence as row 4 | fail |
| 7 | none | "Handing this task to the deep model is an irreversible action ..." | fail |
| 8 | `timeout` | the same sentence as row 4 | fail |
| 9 | `timeout` | "... I am required to get your explicit permission before it can proceed." | fail |
| 10 | none | "To hand this task over to the deep model, I need your explicit approval." | fail |

The baseline passes 0 of 10. In 7 rows the card came and timed out; three replies said the request
was declined, three asked for approval as though nothing had been asked, and one wrote the proof
with no word about the handoff. In 3 rows the model asked for approval in words and never called
the tool, so no card came.

The candidate is `ConfirmAnswer.EXPIRED` with its own result text, `EXPIRED_MSG`
(`cortex_core/untrusted.py`), which says nobody answered in time, that the person did not decline,
and that asking again retries. The same ten rows on a brain built from it, the SM clock reading the
same ratio of its maximum except one row at 0.64:

| Row | Card | Reply's first sentence | Result |
| --- | --- | --- | --- |
| 1 | `timeout` | "The request to escalate this to the deep model expired because it didn't receive an approval in time." | pass |
| 2 | `timeout` | "The request to hand the proof to the deep model expired because it wasn't approved in time." | pass |
| 3 | `timeout` | "The request to hand the task to the deep model expired because no approval was provided in time." | pass |
| 4 | `timeout` | "The request to hand the task over to the deep model expired because I didn't receive an approval in time." | pass |
| 5 | `timeout` | "Here is a rigorous proof that the square root of 2 ($\sqrt{2}$) is irrational ..." | fail |
| 6 | `timeout` | "The request to use the deep model expired because there was no response to the approval prompt in time." | pass |
| 7 | `timeout` | "The request to hand this task over to the deep model expired because the approval request wasn't completed in time." | pass |
| 8 | `timeout` | "The request to the deep model expired because it wasn't approved in time." | pass |
| 9 | `timeout` | "The approval request for the deep model expired because I didn't receive a response in time." | pass |
| 10 | `timeout` | "The request to hand this task over to the deep model expired because the approval request was not answered in time." | pass |

The candidate passes 9 of 10 against the baseline's 0, so it ships. No reply said the person
declined. Row 5 wrote the proof with no word about the handoff, as baseline row 1 did. Every
candidate row called the tool; whether a card comes is decided before any result text exists.

On the shell, with the new build and the 8 s timeout, the same request in a new chat raised the
card, which closed on `confirm_resolved` with nothing drawn in its place, and the reply began "The
previous request to use the deep model for this task expired because no approval was received in
time." The overlay draws no line where the card was: the stored reply now says the request expired,
and a drawn line would be lost when the chat is reloaded. The same reply also said "I have already
provided a standard proof in my previous message", a recalled exchange from another chat taken as
this chat's, the class of the declined
[R-879](../refinements/tasks/879-a-recalled-answer-from-another-chat-is-repeated-as-this-chats.md).

## The brain frozen across a reply and a reminder's due time

`docker pause` froze the brain for 150 s and `docker unpause` thawed it. A freeze stands in for a
machine sleep that the brain's timers count; whether a real sleep of the host is counted is not
measured here. Before the freeze, "Remind me in 90 seconds to check the oven." was set over
`Converse` (due 04:29:34), and on the shell "Please hand this to the deep model: write a short poem
about tides." was sent in a new chat; the freeze began 4 s later, while the cortex was still
writing its first reply.

- **During the freeze** the overlay showed the thinking bubble, and the header dot stayed green 20 s
  in. By the thaw the body had ended the turn on its own 120 s bound, with a red bubble reading
  `no reply within 120s`.
- **At the thaw** the brain logged `inference failed mid-turn` with
  `llama-server sent nothing for model 'cortex' within its ceiling`. That cause is wrong: the read
  deadline ran out while the brain itself was frozen. The chat stored the question and no reply,
  so the question is in the chat list with no answer.
- **The reminder** fired within one poll of the thaw, 68 s after its due time. The push failed
  (`push failed; pull will deliver`, no notification service on `Xvfb`), and the card showed on
  the next new chat as "Check the oven", "2m ago". The age counts from the fire, not from the due
  time, and the card has no due time, so a reminder that fires hours late after a sleep reads as
  fresh. The toast's text had no time either; a late toast's title now names the due time
  ([ADR-0066](../adr/ADR-0066-reminder-toast-and-card.md) decision 11).
- **A card's age while the panel stays open.** Summoned at 04:40:30, 9 min 48 s
  after the fire, the card read "9m ago"; 131 s later, with no input, it still read "9m ago".
  `Reminders.tsx` computed the age once per render and nothing rendered it again until the state
  changed. With the age read from a clock that `useNow` refreshes every 30 s
  ([ADR-0066](../adr/ADR-0066-reminder-toast-and-card.md) decision 6), a reminder that
  fired at 04:48:39 read "2m ago" at 04:51:30 and "4m ago" at 04:53:14, with no input between.

## A reminder months ahead across a restart of Redis and the brain

"Remind me on 14 March 2027 at 10:00 to renew the passport." stored one item. Redis and then the
brain were restarted (`docker restart`, 04:33:18 and 04:33:19). "Which reminders do I have
scheduled?" then listed it with its due time, and the oven reminder as fired and awaiting delivery.
Nothing was lost: Redis reloads both from its append-only file.

## Not run

- **The tool rest window ending while a turn is in flight.** A turn lists its tools once, at its
  start, so a turn that starts inside the rest has no filesystem tools for its whole length
  whether or not the rest ends during it; the turn inside the rest is in
  [overlay-tool-failure-flows.md](overlay-tool-failure-flows.md). This reading is of the code, not
  a run.
- **A card open across the freeze.** The cortex had not yet asked for the card when the freeze began,
  so the card's 120 s timeout was not exercised across it.

## Defects filed

- [R-906](../refinements/tasks/906-a-late-reminder-does-not-say-when-it-was-due.md): a reminder that
  fires late shows only its fire time on the card.
- [R-909](../refinements/tasks/909-a-frozen-brain-blames-llama-server-for-a-lost-reply.md): a turn
  frozen past the stall bound blames llama-server.
