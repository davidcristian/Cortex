# Readings: a tool call cut off by a stopped sidecar

What the cortex replies when the tool server it is calling stops in the middle of the call. The
text the model reads for that call depends on `CORTEX_TOOLS_ON_UNAVAILABLE`. Under `fail` the
dispatcher hands it the `ToolError` text `MCP sidecar unavailable`, and in the
[outage flows](store-and-sidecar-outages.md#the-filesystem-sidecar) the model blamed the file and
quoted that text. Under `skip`, the default, it reads `unknown tool 'read_text_file'`: the
aggregate registry routes each call by listing every sidecar again, and the stopped one now lists
nothing. This record holds the rows and the pass rule for changing that text, written before any
baseline row was drawn.

## The rig

The GPU stack under its own compose project, gemma 12B as the cortex, `CORTEX_TOOLS_ON_UNAVAILABLE`
at `skip`, the filesystem sidecar over a tools root holding `choir-rota.txt` (a heading and four
lines, `Week 1: Anna` to `Week 4: Dora`). Each row is one new session over `Converse` from the
host. Memory rows that mention the rota or the sidecar are deleted before each row, so no row
recalls another. A watcher pauses `mcp-filesystem` as soon as the brain logs the tool audit of a
`list_directory` call, and kills it 8 s later, so the next file read is cut off; the sidecar is
started again, and listening, before the next row.

## The rows

- **Prompt**, the same in every row: "Read choir-rota.txt in my files and tell me who sings in
  week 2."
- **Baseline**: the current tree, 5 rows.
- **Candidate**: 5 rows on a build where a call that a stopped sidecar cuts off returns, in place of
  either text above, the error text "the filesystem tool server stopped answering during this
  call, so the call did not finish; this says nothing about the file or item the call named",
  with the server's configured name in place of `filesystem`.
- **A row counts** only when the tool audit shows a file read that started after the pause and
  ended with `ok=False`. A row without one is void and is drawn again, at most twice.
- SM clock read after each phase with `nvidia-smi`.

## How a reply is classed

Each reply is read against these definitions, and may fall in more than one class.

- **Names the tool**: says that the file tool, the tool server or the file server stopped, failed
  or is not answering.
- **Blames the file**: says the file itself is unavailable, inaccessible, missing, empty or damaged,
  or that its content is the error, without naming the tool or its server as the cause.
- **Quotes the error**: contains `MCP sidecar unavailable`, `unknown tool` or the word "sidecar".
- **Loops**: repeats one sentence or one plan to call a tool three times or more, or stops at the
  length limit.
- **Invents**: names who sings in week 2, or any rota line, without a tool result that held it.

## The pass rule

- **The defect reproduces** when at least 3 of the 5 baseline rows blame the file, quote the error
  or loop. Otherwise the candidate is not run on this evidence, and the task is checked again with
  a different prompt.
- **The candidate ships** when at least 4 of its 5 rows name the tool, and none blames the file,
  quotes the error, loops or invents. Any other result keeps the current text, and the rows are
  recorded here.
- A status naming the stopped server, sent to the body when such a call fails, is not text the
  model reads and is decided apart from these rows.

## Results

**2026-10-13, a probe row**, drawn before these classes and this rule were written, so it is not
a baseline row. The cut off `read_text_file` call ended with `unknown tool 'read_text_file'`. The
model then called `read_file`, `read_text_file` and `list_directory`, each failing as an unknown
tool or a repeated call, and wrote its plan into the reply: "I'm encountering errors when trying
to read it. I'll try to read it again", then "Actually, I'll try `read_text_file` again." and
"Actually, I'll try `read_file`." in turn until the reply, 3,764 words, stopped at the length
limit 169 s into the turn.

Method: the drivers in the run's scratch directory, `docker logs` of the brain for the tool audit,
and the replies read against the classes above.
