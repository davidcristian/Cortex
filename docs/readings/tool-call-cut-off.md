# Readings: a tool call cut off by a stopped sidecar

What the cortex replies when the tool server it is calling stops in the middle of the call. The
text the model reads for that call depends on `CORTEX_TOOLS_ON_UNAVAILABLE`. Under `fail` the
dispatcher hands it the `ToolError` text `MCP sidecar unavailable`, and in the
[outage flows](store-and-sidecar-outages.md#the-filesystem-sidecar) the model blamed the file and
quoted that text. Under `skip`, the default, with one sidecar configured it reads the same text.
With two or more it reads `unknown tool 'read_text_file'`: the aggregate registry routes each call
by listing every sidecar again, and the stopped one now lists nothing. This record holds the rows
and the pass rule for changing that text, written before any baseline row was drawn.

## The rig

The GPU stack under its own compose project, gemma 12B as the cortex, `CORTEX_TOOLS_ON_UNAVAILABLE`
at `skip`, the filesystem sidecar over a tools root holding `choir-rota.txt` (a heading and four
lines, `Week 1: Anna` to `Week 4: Dora`), and the email sidecar beside it, so the aggregate
registry routes each call. Each row is one new session over `Converse` from the
host. Memory rows that mention the rota or the sidecar are deleted before each row, so no row
recalls another. A watcher pauses `mcp-filesystem` as soon as the brain logs the tool audit of a
`list_directory` or `search_files` call, the two ways the model finds the file, and kills it 8 s
later, so the next file read is cut off; the sidecar is started again, and listening, before the
next row.

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

**2026-10-13, a first draw** of 5 rows with a watcher that waited for `list_directory` alone, so
it is not the baseline either. In 4 rows the model found the file with `search_files`, the read
was never cut off, and each replied "Bela sings in week 2." In the one row cut off, the model
called `read_text_file` and `read_file` four times between them, each failing as an unknown tool
or a repeated call, until the round limit ended the turn with its note naming the failed reads,
22 s in. That reply neither names the tool server nor blames the file. SM clock 0.59 of
`clocks.max.sm` after the draw.

**2026-10-13, the baseline**, 5 rows on the current tree, every one counted on its first draw
(the model found the file with `search_files` in 4, `list_directory` in 1). Each cut off read
ended `unknown tool 'read_text_file'`, and the model then tried `read_file` and others, each an
unknown tool.

| Row | Reply, in short | Classes |
| --- | --- | --- |
| 1 | the read tools "returned an "unknown tool" error"; check the path or the file's restrictions | quotes the error, names the tool |
| 2 | the round limit's note, after three `read_text_file` calls | loops |
| 3 | "my tools for reading and listing files are not currently responding" | names the tool |
| 4 | "encountering some issues with the file system tools" | names the tool |
| 5 | "I don't have the ability to read local files" | none |

2 of 5 rows blame the file, quote the error or loop, under the 3 the rule needs, so **the defect
does not reproduce** with this prompt and the candidate is not run on this evidence. 3 of 5
replies already name the tool, and none blames the file or invents. SM clock 0.59 of
`clocks.max.sm` after the baseline.

Method: the drivers in the run's scratch directory, `docker logs` of the brain for the tool audit,
and the replies read against the classes above.

## A rule decided on the code

**2026-10-14, written before the change it calls for.** No row can decide the `unknown tool`
text, because it is false whatever a model does with it: the tool was in a listing, and the
aggregate cannot route the call only because the server that listed it is not answering. The rule:
when no live listing holds a call's tool and a skip wrapped server's last good listing held it,
the call returns the error text `the <server> tool server is not answering, so '<tool>' did not
run`, with the server's configured name. `unknown tool` stays for a name no server listed and for
one that an answering server dropped. The text says only what the code knows, that the call was
never sent. The candidate's further clause, that the text says nothing about the file, is a steer
for the model and stays the rows' question. The one sidecar path keeps `MCP sidecar unavailable`,
which is accurate.

**The next rows**, written before they are drawn: 5 rows on the build with this text, with the rig,
prompt, classes and void rule above, and a reply that ends with the repeated line note counted as
a loop. They do not decide the text above. They decide the candidate's clause: when at least 2 of
the 5 rows blame the file, quote the error, loop or invent, the clause is added and run as the
candidate rows; otherwise the task closes without it.

**2026-10-14, the next rows**, 5 on the build with the text above. Row 5 counted on its third draw:
in the first two the model's `search_files` was refused for a path outside the tools root, so the
call cut off was `list_allowed_directories` and no file read. In every counted row the cut off read
and each later file call ended with the new text. The model then tried `read_file`,
`list_directory` or the same read again, the dispatcher refused a third identical read in row 1,
and in row 5 the model also handed the read to a subagent, which came back without the file.

| Row | Reply, in short | Classes |
| --- | --- | --- |
| 1 | the file "could not be read because the filesystem tool server is not responding" | names the tool |
| 2 | "The `read_text_file` tool is currently failing to retrieve the content" | names the tool |
| 3 | "having trouble accessing the file" because the tool server "is not responding" | names the tool |
| 4 | "unable to read the file" because "the filesystem tool server is not responding" | names the tool |
| 5 | "the filesystem tools are not responding correctly"; asks for the file's text | names the tool |

0 of 5 rows blame the file, quote the error, loop or invent, under the 2 the rule names, so the
candidate's clause is not added. SM clock 0.59 of `clocks.max.sm` after the rows.

## One sidecar

With only the filesystem sidecar configured there is no aggregate. The skip wrapper passes a call
straight to the adapter, so a call cut off reads `MCP sidecar unavailable`, or the deadline's text
when the server stays paused past it. That text is accurate, and it is the text the model blamed
the file for in the [outage flows](store-and-sidecar-outages.md#the-filesystem-sidecar).

**Rows**, written before they are drawn: the rig above without the email sidecar, so the brain
has one tool server, with the same prompt, classes and void rule, 5 rows on the current tree.
**The defect reproduces** when at least 3 of the 5 blame the file, quote the error or loop. Then a
candidate that names the server for a call cut off on this path is designed and run as 5 rows
under the candidate's pass rule above. Otherwise the text stays and the rows are recorded here.
