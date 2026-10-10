# Readings: delegation through the overlay on the Linux shell

What the overlay showed, what the store held and what the brain and the subagent servers logged
when a person asked for delegated work, stopped a delegated turn, and lost a subagent server in the
middle of one. The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless) with procedure 6
of [the delegation runbook](../runbooks/subagents-validation.md) for the stack. A plain turn
stopped or cut is in [overlay-turn-flows.md](overlay-turn-flows.md).

## The rig

**2026-10-10**, a debug build of the shell from the tree with the overlay embedded, WebKitGTK
drawing in software on an `Xvfb` display, against `docker/docker-compose.yml` with the `gpu`,
`subagents` and `subagents-roster` overrides: the cortex on the card, the default subagent entry
(gemma-4-E4B, build `b10680-d7bd3bfca`) and the roster entry `qwen` (Qwen3.5-2B) each on its own CPU
server, no tools. Bringing both CPU servers up left the card at 9903 MiB used of 24463 before and
after, at 0 % utilisation. Each turn was typed into the panel with `xdotool`; frames, the brain log
and both servers' logs were read beside the Redis records.

## A request that invites delegation

- **What the panel shows while subagents run.** Under the question, one chip names the call and
  the start of the tool's description (`spawn_subagents: Delegate one or more narrow subtasks to
  s...`), and a second chip counts the batch: `2 subtasks running, 1 waiting for room to run` for
  three items, which is the admission budget (4.0 CPUs, 2.0 a subtask) admitting two. Both chips
  fold into `Thoughts` when the reply starts.
- **A role with no text to apply to.** Asked to have one subagent say what a lighthouse is for,
  one list three famous lighthouses and one explain the lens, the cortex named the `answer` role on
  all three items with no `context`. Each subagent replied only that the text does not state it
  (`The text does not state it.`, 171 characters for the three), and the cortex told the person the
  subagents could not answer and answered from its own knowledge. A second turn asking for three
  250-word paragraphs named `answer` on all three again, with the same reply on the one that
  finished. The runner now adds a role's sentence only to a subtask with a context
  ([ADR-0072](../adr/ADR-0072-subagent-roles.md) decision 1). On a brain with that change, a
  question the cortex delegated as two `answer` items with no context drew both answers, two
  sentences each, and the reply gave them as written.
- **A draw with no role.** Asked again on a brain with that change, the lighthouse question drew no
  role. Two subtasks answered; the third ran to the 1024-token cap and came back as a failure. The
  reply relayed the two answers as written, including `Eiffel` among the famous lighthouses, said
  the first subagent failed, and wrote "I will retry that specific task" in a turn that ended
  without a retry. Drawn again eleven times, that did not recur
  ([below](#a-subtask-cut-at-the-cap-a-promised-retry-against-a-retry)).
  A third question, two sentences each on tides, volcanoes and glaciers, drew no role either; one
  subtask ran to the cap and the reply said so accurately.
- **The cap runs are the garbled channel marker.** Sent straight to the default server with the
  reply envelope and a cap of 300, the tides subtask came back empty at the cap at seeds 1 and 2,
  its text in `reasoning_content` after an opening `t</c>`. That is the defect
  [ADR-0049](../adr/ADR-0049-thinking-switch-and-trace-budget.md) decision 10 records and leaves to
  the subagent pick. Over these turns 2 of 6 live subtasks hit it, and each one held the turn until
  it had decoded all 1024 tokens.

## Stop during a delegated run, then a second turn at once

- **The subagents stop with the turn.** Stop was pressed 6.2 s after the first subagent request of
  a three-item batch. The default server logged `stop: cancel task` for both running requests and
  released both slots, and both servers' `/slots` read idle at the first poll, 1.4 s after the
  Stop. One subtask had finished before the Stop.
- **The next turn runs cleanly.** `Name two rivers, one line.`, sent 1.3 s after the Stop, was
  stored 3.1 s later with its reply. The next delegated turn admitted both of its items at once, so
  the cut subtasks released their admissions.
- **The store.** The cut turn holds the question only: no reply and no `runs`, which matches a plain
  stopped turn. Of its three task records, the finished one has its result and the two cut ones
  have none, and the brain wrote no audit line and no log line for the cut spawn. The dispatcher
  now audits a call cut by a cancel before the cancel goes on: run again on a brain with that
  change, a two-item batch stopped 4.2 s after its first subagent request wrote one
  `spawn_subagents` audit line with `ok=False` and `error="cancelled: the turn ended before this
  call returned"`, and the next turn answered in 3.0 s. A cut subtask still keeps no result: its
  task record names its turn, and a store write under the cancel would put a Redis write in front
  of every Stop.
- **The panel** shows the stopped turn as `Thoughts` over an empty reply bubble, and the second
  turn under it.

## A subagent server killed during a delegated run

- **The turn ends at once and says why.** `docker kill -s KILL` on the default server, 5 s into a
  two-item batch, failed both requests. For the subtask placed on the GPU target the runner logged
  `a GPU-placed subagent did not answer; re-running it once on the CPU`, and the re-run failed at
  once, since both placement targets of the default entry are that one server in this stack. The
  CPU-placed subtask failed with no re-run, and its stored result keeps the partial raw envelope
  (`{"reply": "Volcanoes are...`) as `output`, which the tool does not show the cortex. The reply
  was stored under a second after
  the kill: "The subagents were unable to generate the paragraphs due to a server error. Please try
  again in a few moments." The audit line reads `ok=True`, the tool having returned the two failed
  results as values.
- **The panel names the server down as a note.** `Health` asks each roster entry's CPU server
  every 2 s ([ADR-0054](../adr/ADR-0054-baseline-residency.md) decision 8). After `docker kill -s
  KILL` on the `qwen` server it answered `ready=True` with "the server for subagent model qwen did
  not answer within 1 s" for about 10 s, then
  "the server for subagent model qwen is not answering, so work delegated to it fails". The dot
  stayed green, and hovering it showed `Brain ready` over that line. `docker start` brought a
  "still loading" note and then the plain detail, 13 s after the start.
- **A crash restarts the server, `docker kill` does not.** `docker kill` counts as a manual stop
  under `restart: unless-stopped`, so the server stayed exited until started by hand. A `SIGKILL`
  sent to the server's process from the daemon's own process namespace (`docker run --pid=host
  --privileged`), which is how Docker sees a crash or an out-of-memory kill, exited it with 137,
  and Docker started it again within a second (`RestartCount` 1); its `/health` answered 200 13 s
  after the kill.

## A subtask cut at the cap: a promised retry against a retry

**Rows, written before the first run.** Each row is one turn sent to the brain over `Converse`
with `CORTEX_SUBAGENTS_MAX_TOKENS=160`: "Use subagents in parallel for this: one writes a 400-word
essay on the history of lighthouses, one names the largest ocean in one word, and one names the
longest river in one word." A row is valid when the turn called `spawn_subagents` and the essay
subtask's stored result is the cap failure. A valid row **promises** when its reply says the
assistant will retry, re-run or delegate the failed part again, read by hand with a regex as a
first screen, and the turn makes no further `spawn_subagents` call. Five rows on the shipped text
(A), then five on the changed text (B), each in a new chat.

**Pass rule.** B ships when at least four of its rows are valid, none promises, and every valid
reply either delegates again in the turn, answers the essay itself and says so, or says it is
unanswered. A run of A with no promise means the defect does not recur at this condition, and the
text stays as it is.

**A, 2026-10-10, five rows, SM clock 0.59 of max at the start.** Five valid, none promised. Three
replies said the essay stopped at the token limit and gave the other two answers, two of them
offering to split the essay if the person asked. One wrote the essay itself and did not say the
subagent had failed. One delegated again in the turn, splitting the essay into two halves with a
`context`; both halves came back `The text does not state it.`, and the reply said the essay could
not be done. A one-word subtask also stopped at the cap in that row, with an empty reply.

**Rows A2, written after A and before their run.** The question of the original report ("Use
subagents in parallel for this: one summarizes in two sentences what a lighthouse is for, one lists
three famous lighthouses, and one explains in two sentences how a lighthouse lens works.") at the
shipped cap of 1024, drawn eight times on the shipped text. Valid rows are those where a subtask
comes back as the cap failure; the promise test is A's. A2 decides only whether the promise recurs
when a short subtask is cut, which the cap detail does not explain.

**A2, 2026-10-10, eight rows, SM clock 0.59 of max at the start and the end.** Six valid: 9 of the 24
first-round subtasks stopped at the cap, two-sentence and one-line subtasks alike, each holding its
turn for its whole 1024 tokens, so a valid row took 112 to 244 s. Two replies wrote "I will now
retry that specific subtask" and "I will re-run that specific task", and both turns did delegate the
failed subtask again before the reply ended. Of the other four, one delegated again without saying
so, one answered both failed parts itself after saying the subagents had failed, and two gave only
the answers that came back and named the failed parts. No valid row promised a retry it did not
run. The famous-lighthouse subtask named the Eiffel Tower in five of the eight rows; three replies
said it is not a lighthouse, and two relayed it as one.

**Result.** No promise without a retry in eleven valid rows over A and A2, so by the rule above the
cap detail stays as shipped. The one report of a broken promise is a single draw; a second one
seen anywhere is the trigger to run B.

Method: `xdotool` typing into the panel, frames from `ffmpeg -f x11grab`, the brain log, each
server's `launch_slot_`, `print_timing` and `stop:` lines and `GET /slots`, and the Redis keys
`cortex:session:<id>:messages` and `cortex:task:<id>` with its `:result`.
