# A handoff that a restart of the brain ends

What a chat's store holds, what the next replies say, and what the overlay shows, after the brain's
container is killed in the middle of a handoff to the deep model. Decisions 3 and 6 of
[ADR-0074](../adr/ADR-0074-replayed-tool-runs.md) rest on it.

## Reading, 2026-11-18

The default stack with escalation on, the Qwen3.8-27B Q4 deep tier, the model host on build
`b12375` and a brain image built from the tree. One draw per row. Method: `live.sh` in
`~/.cache/cortex-run/2026-11-18/slot13/` sends each turn with `turn13.py`, kills the brain's
container once the deep tier answers `ready`, starts it again and reads the chat's list from
redis; the log is `logs/live.txt` beside it.

Chat A, whose handoff the kill ended:

| Step | What was read |
| --- | --- |
| The handoff turn, cut by the kill | memory row with `Tools run: escalate_to_brain (handoff started, answer not recorded here)` |
| Boot | the brain logged `a handoff did not survive the restart; marking it failed`; the deep tier was stopped and the cortex and both GPU subagent servers answered `ready` |
| The chat's list in redis after the restart | three messages: the request, the cortex's reply with the run `escalate_to_brain` `ok: true`, and a third reply of the same turn with the run `escalate_to_brain` `ok: false` and the text of `UNANSWERED_HANDOFF_NOTE` |
| Next turn, `What is 5 plus 5?` | `5 plus 5 is 10.` with `UNANSWERED_HANDOFF_NOTE` under it |
| The turn after it, `And what is 6 plus 6?` | `6 plus 6 is 12.` and no note |
| A new chat, `What did I last ask you to hand to the deep model, and did it finish?` | the cortex named the request, said it did not finish because the assistant restarted during the handoff, and offered to hand it over again |

Chat B, whose handoff completed on the same stack after the restart:

| Step | What was read |
| --- | --- |
| The handoff turn | the cortex's sentence and the deep model's answer in one reply; two memory rows, the cortex's with the `handoff started` line and the deep model's with no `Tools run` line |
| Next turn, `What is 7 plus 7?` | `7 plus 7 is 14.` and no note |
| The chat's list in redis | five messages, none with a failed `escalate_to_brain` run |

The new chat's reply in chat A's table is the model's own reading of two recalled memory rows: no
check of the brain's produced it ([R-1257](../refinements/tasks/1257-a-handoff-a-restart-ended-is-told-only-in-its-own-chat.md)).

## The overlay's view, 2026-11-24

The same stack shape with no memory store: the default compose file with the GPU and loopback
overrides, escalation on, the Qwen3.8-27B Q4 deep tier, the model host on build `b12375` and a
brain image built from the tree. One draw. Method: `crash.sh` in `~/.cache/cortex-run/2026-11-24/c2/`
sends the handoff turn through Converse in a known chat with `turn.py`, kills the brain's container
once the deep tier answers `ready`, and starts it again. Boot recovery logged `a handoff did not
survive the restart; marking it failed` and wrote the record itself. The overlay ran from
`npm run dev` in headless Chromium (Playwright's `chromium_headless_shell-1228`) with an init script
that defines `window.__TAURI_INTERNALS__`, so `main.tsx` mounts `TauriBridge`. Its `invoke` reaches
`relay.py`, which makes the gRPC calls the Rust commands make and maps the fields as
`body/crates/rpc/src/sessions.rs` does. The next turn went through Converse from `turn.py`, not the
composer, and the page was loaded again after it. The screenshots are in `shots/` beside the
scripts.

The pass rule, written in [R-1315](../refinements/tasks/1315-nobody-has-looked-at-a-chat-a-restart-ended-in-the-overlay.md)
before the look: the switcher row shows the record's text, and a reader of the restored chat sees
the text once.

| Step | What the overlay showed |
| --- | --- |
| Summon after the restart | the chat restored on mount: the request, the cortex's reply, and the record as a third bubble |
| The switcher, before the next turn | one row, titled with the request, previewed with the record's first 96 characters |
| Next turn, `What is two plus two?` | `Two plus two is four.` with the record's text under it, in the stream and in the store |
| The switcher, after it | the row previewed with the new reply, which begins `Two plus two is four. (The assistant restarted` |
| The restored chat, after it | the record's text twice: the record's bubble and the end of the new reply |

The switcher half of the rule passes and the restored-chat half fails. Which copy the overlay shows
is the open choice in R-1315.
