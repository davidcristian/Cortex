# The reader's thought vocabulary is a hand list held to nothing the model files say

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a pick entering the lineup whose chat template writes a thought marker
`scripts/switchtail.py` does not list, or a model file of a listed family whose template changes
the marker it writes. Both are countable by the struct walk over each GGUF header's
`tokenizer.chat_template` that opened this entry: count the chat templates on the mount and the
markers they write, and compare a file's template against a recorded reading of that same file.

Opened 2026-09-02 by the close of
[R-517](517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md), which read
every chat model file on the mount for the markers its template writes and found two pairs and
no third.

`MARKERS` in `scripts/switchtail.py` is two pairs typed by hand, `<think>`/`</think>` and
`<|channel>thought`/`<channel|>`, and nothing holds them to the lineup. The templates that write
them are readable without a server: each GGUF carries its own `tokenizer.chat_template` in the
file header, and reading it is a struct walk over the key-value block, which is what the close
above did to settle whether a third pair existed. So the vocabulary could be a recorded answer
held to that reading, in the shape `scripts/imagevolumes.py` takes for what an image declares: a
committed record of the markers each lineup file's template writes, a gate that holds `MARKERS`
to the record, and a hand-run recipe that re-derives the record from the mount, since the gate
cannot reach `/mnt/ai/Models` any more than it can run docker.

Two residues of the close above would fall to the same pair, whichever way it arrives. A switched
tail closed in an unlisted marker that the key changed is refused as an unrecognized format, in
the right words; one rendered identically both ways is read as an open thought, and if its control
fires anyway, which needs the model to open a thought of its own after the prompt closed one, the
run is refused as a broken prediction and sent to the record rather than to the vocabulary. Both
are a pair short, and neither has a template to be measured against: every file on the mount is
one of the two families, and the Qwen3.8 entries that are not yet in the lineup write `<think>`
and read `enable_thinking` the way the Qwen3.6 files do. Adding the pair when the pick arrives is
one line; the record and the recipe are what make that line checked rather than trusted.

## Trail

- 2026-09-02: opened by the close of
  [R-517](517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md), whose
  ADR-0005 quiet-control addendum records the 17 chat model files read and the two pairs found.

- 2026-09-04: re-derived and still open. Neither half of the trigger has fired. Walking every
  `*.gguf` on `/mnt/ai/Models` reads 68 files, 34 with a chat template, and all 34 write a pair
  `MARKERS` already lists: 8 gemma-4 files write `<|channel>thought` and `<channel|>`, and 26 Qwen
  files write `<think>` and `</think>`. The 17 files above the quiet-control table's 17 are
  uncensored repackages and MTP variants of families already listed there. The walk also turns up
  `<|think|>` on every gemma-4 template, which `MARKERS` does not carry: it is written at the top
  of the first system turn and never in the tail `switchtail.tail` reads, so it is out of scope by
  position. For the second half, the tree holds one recorded template reading, the 7,816 characters
  the served-by addendum records for `unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf`, and the
  header gives 7,816 today; the other 33 files have nothing to be compared against, which is the
  record this entry asks for. The ADR-0005 mount-walk addendum of the same date carries the table.
