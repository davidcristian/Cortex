# A recall question memory cannot answer searches the file sidecar

**Status:** declined 2026-11-12
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)

On 2026-11-11 the `cortexn19` stack answered `What is my bike lock code?`, sent as the first
message of a new chat, with file sidecar calls (`list_allowed_directories`, `list_directory`,
`read_text_file`, `search_files`, `directory_tree`) in 12 of 24 recorded turns. All 12 are the
turns whose first request held no recalled row naming the bike lock (chats `n19s15-q-n1` to `n6`
and `n19s16-q-1` to `6`). None of the 12 turns whose first request held that row (`n19s15-q-r1`
to `r6`, `n19s15-c-q1` to `q6`) called any tool. File tools were offered in the first request of
all 24. The counts come from the proxy log of that
night (`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/stack/logs/proxy/all.jsonl`). A turn that reads a file is tainted, so memory does not keep it, and an update such as
`Update my gym locker number: it is 5512, not 5521.` searched files until the round cap
([R-1116](1116-an-update-of-a-stored-value-can-search-files-until-the-round-cap.md)).

The premise to check first: did the store hold a bike lock row in the 12 calling chats? If it
did, recall missed it and the defect is in recall. If it did not, a search of the person's files
for a code memory does not hold may be what the person wants, and no refusal is due.

## What to do

1. Read the `cortexn19` stores and the slot notes for the `q-n` and `s16-q` rows to decide which
   of the two cases above they are.
2. If file calls on such a question are a defect, add a refusal `unasked_sidecar_tools` beside
   `unasked_forget` (`unasked_tools.py`) that withholds the file tools on a question naming no
   file, folder, note or document. Its safe direction keeps the tool: any file word, path or
   file name in the message keeps them offered. Write near-miss questions as tests first
   ("What is in my notes?", "Which file has my lock code?").
3. Replay the recorded first requests through it and count the turns it would change.

## History

- 2026-11-11: filed from R-1116 and the recall draws of that night, with the counts above.
- 2026-11-12: declined. The store held no bike lock row in any of the 12 calling chats: they are
  the no row condition of the
  [recall draws](../../readings/correction-keeps-old-value.md#the-question-in-a-new-chat-2026-11-11)
  and the [question draws](../../readings/forget-unrequested.md#the-draws-2026-11-11), each drawn
  after a reset of the store, and every reply said accurately that no file holds the code. A search of the files the person allowed is
  then what the question can ask for, and a refusal would lose it where a notes file holds the
  value. The turn is tainted, so `memory_withheld` (`memory_claim.py`) keeps the exchange out of
  memory unless the deployment records tainted turns; a question's exchange holds no fact to lose.
  The case that lost a fact, an update searching files, was closed in R-1116.
