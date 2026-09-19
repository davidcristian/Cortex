# The reader's thought vocabulary is a hand list checked against nothing the model files say

**Status:** open, waiting for its trigger
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)
**Verified:** 2026-09-15
**Trigger:** a pick entering the lineup whose chat template writes a thought marker
`scripts/switchtail.py` does not list, or a model file of a listed family whose template changes
the marker it writes. Both are countable by the struct walk over each GGUF header's
`tokenizer.chat_template` that opened this entry: count the chat templates on the mount and the
markers they write, and compare a file's template against a recorded reading of that same file.

`MARKERS` in `scripts/switchtail.py` is two pairs typed by hand, `<think>`/`</think>` and
`<|channel>thought`/`<channel|>`, and nothing compares them with the lineup. The templates that
write them are readable without a server: each GGUF has its own `tokenizer.chat_template` in the
file header, and reading it is a struct walk over the key-value block. So the vocabulary could be a
recorded answer compared with that reading, in the shape `scripts/imagevolumes.py` takes for what an
image declares: a committed record of the markers each lineup file's template writes, a check that
compares `MARKERS` with the record, and a hand-run recipe that recomputes the record from the mount,
since the check cannot reach `/mnt/ai/Models` any more than it can run docker.

The record has to say what a template emits, not what it mentions. Six of the 34 templates on the
mount have thought markers they only read: `<thinking>` and `</thinking>` in the branch that splits
a previous assistant message into reasoning, and the sentinels `<|think_on|>` and `<|think_off|>`
that they strip out of a system message. A record scanning each template's text for marker-shaped
strings would list all four, and a vocabulary using them would read a thought as closed on text no
model writes. The literals inside a template's output expressions are what it emits, and that is
derivable from the template's own syntax.

## History

- 2026-09-02: opened by the close of
  [R-517](517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md), whose close
  read 17 chat model files and found two pairs (thinking-switch readings).
- 2026-09-04: checked again and still open. Walking every `*.gguf` on `/mnt/ai/Models` reads 68
  files, 34 with a chat template, and all 34 write a pair `MARKERS` already lists: 8 gemma-4 files
  write `<|channel>thought` and `<channel|>`, and 26 Qwen files write `<think>` and `</think>`. The
  walk also turns up `<|think|>` on every gemma-4 template, which `MARKERS` does not have: it is
  written at the top of the first system turn and never in the tail `switchtail.tail` reads. For the
  second half, the tree has one recorded template reading, the 7,816 characters recorded for
  `unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf`, and the header gives 7,816 today; the other 33
  files have nothing to be compared against.
- 2026-09-13: checked again and still open. `MARKERS` is the same two pairs. `/mnt/ai/Models` holds
  the same 68 `*.gguf` files, none written since the walk above, so no pick has entered the lineup
  with a marker to add.
- 2026-09-15: checked again and still open, and the proposed record is corrected above. The same 68
  files, 34 with a `tokenizer.chat_template`, none written since 2026-09-04, and every one of the 34
  still writes a pair `MARKERS` lists. The walk was compared with a running server for the first
  time: the template `GET /props` serves for `unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf` and
  the template that file's own header has are the same 7,816 characters under the same SHA-256, so
  an offline reading and a served one are one answer. What the walk turned up is the distinction
  written into the body above: the six uncensored Qwen3.6 repackages mention two thought markers
  and two sentinels they never emit, and all eight gemma-4 templates emit `<|think|>` at the top of
  the first system turn and never in the tail this reader takes (ADR-0050 decision 4).
