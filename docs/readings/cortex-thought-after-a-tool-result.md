# Readings: the cortex's thought after a tool result

Whether the cortex writes a thought (`reasoning_content`) on a round that follows a tool result,
and whether its reply is then its working instead of an answer: text such as `The user's request
has two parts: ...` and `Wait, let me re-read the forget_memories tool definition`, streamed to
the person as the reply. The thinking settings are
[ADR-0049](../adr/ADR-0049-thinking-switch-and-trace-budget.md); the remedy these rows point to
is [R-1392](../refinements/tasks/1392-send-the-cortex-thought-back-with-its-tool-calls.md).

## The typed form

A reply is counted as working when its own text (before the first brain note, the paragraph that
opens with `(`) matches any of:

1. it opens with `The user` or `The user's` followed by `request`, `wants`, `wanted`, `asked`,
   `is asking` or `has asked`;
2. it holds `Wait,` and the name of an offered tool (`schedule_task`, `list_scheduled`,
   `cancel_scheduled`, `snooze_scheduled`, `edit_scheduled`, `forget_memories`);
3. it is longer than 1,500 characters and names an offered tool.

The rule, the shapes and what each count decides were written before the first draw.

## The stack, 2026-11-28

- Brain image built from the clean tree, the tree's `cortex_core` bound over its package. Model
  host `cortex-model-host` on compose defaults, never built, the tree's model manager and core
  bound over its packages. Engine build b12375.
- The argv the model host wrote: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, context 16,384, `--jinja`,
  no cache type flag (the default), the MTP drafter `mtp-gemma-4-12B-it-Q8_0.gguf` at a draft
  length of 3, no `--reasoning-budget` and no reasoning effort flag.
- `CORTEX_SCHEDULE_BACKEND=redis`, every other setting at its default. Put back before every
  draw: the two memory rows and the tainted reminder of
  [the later taint draws](forget-later-taint.md).
- A recording proxy between the brain and the cortex sets the sampling seed on every request and
  applies the variant. Thought tokens are counted by the cortex server's own `/tokenize`.

## What the template does

The pick's chat template (`chat_template` in the server's `/props`) puts `<|think|>` in the
system turn when thinking is on, which it is when the request sends no `enable_thinking`. After a
tool result it ends the prompt with `<|channel>thought`, so the thought is opened inside the
prompt and the model chooses whether to write in it; a `--reasoning-budget` never sees that
thought start. A thought sent back on an assistant message (`reasoning_content`) is rendered
before that message's tool calls. The brain sends none.

## The recorded runs

Two earlier runs of the same night, read again from their proxy logs: a thought on 75 of the 75
requests that end with the person's message, and on 47 of the 88 that end with a tool result.
The three working replies (1,931 to 6,685 characters) all came from a final round with no
thought. The typed form marks all three and none of the 69 other replies.

## The draws

16 draws per row, seeds 0 to 15, one new chat each, every card approved. P is `What is the
boiling point of water at sea level in Celsius?`, F `Cancel my reminder nope-1.` (one call, which
fails), C `Forget my old locker code 4242. Remember that my new locker code is 5151. Then list my
reminders.`, N `Remember that my new locker code is 5151. Then list my reminders.` V sends each
round's thought back on its assistant message; W sends `enable_thinking: false` on every request
whose last message is a tool result.

| Shape | Variant | Working replies | Final rounds after a tool result with no thought | Thought tokens per reply, median (range) |
| --- | --- | --- | --- | --- |
| P | none | 0 of 16 | no tool result | 41 (30 to 64) |
| F | none | 0 of 16 | 9 of 16 | 90 (29 to 198) |
| C | none | 0 of 16 | 4 of 16 | 1,461 (303 to 3,219) |
| N | none | 1 of 16 | 7 of 16 | 523 (95 to 2,067) |
| F | V | 0 of 16 | 0 of 16 | 104 (58 to 161) |
| C | V | 0 of 16 | 0 of 16 | 1,141 (612 to 1,674) |
| N | V | 0 of 16 | 1 of 16 | 691 (331 to 938) |
| F | W | 0 of 16 | 16 of 16 | 67 (29 to 95) |
| C | W | 0 of 16 | 16 of 16 | 448 (231 to 660) |

- The working reply on N (seed 1, 1,144 characters) came from a final round with no thought,
  after `list_scheduled` and two failed `schedule_task` calls: no tool stores a fact, and the
  model wrote out how to answer a request its tools do not cover.
- Every F call failed (`no scheduled item nope-1`). C called `list_scheduled` in 15 of 16 draws
  with no variant, 16 of 16 under V and 12 of 16 under W: under W four replies answered the
  forget and skipped the listing the message asked for. N listed in 16 of 16 with and without V.
- Under V every round after a tool result on F and C streamed a thought, the middle rounds of a
  three-round turn included.

What the counts decided, by the rule written before the draws: P at 0 places the form on rounds
after a tool result, and the one working reply drawn came from a final round with no thought.
F and C at 0 of 32 cannot show a variant removing the form. V leaves 1 of 48 final rounds without
a thought where no variant left 20 of 48, and W drops a requested listing, so V is the remedy
proposed. Its cost on these shapes: the median thought tokens per reply is 0.8 to 1.3 times the
no-variant row's.

## Method

The scripts are in `~/.cache/cortex-run/2026-11-28/s7/`: `base.sh`, `variants.sh`, `nshape.sh`
and `nv.sh` draw the rows, `proxy/proxy.py` applies the variant named in `proxy/variant`,
`tally.sh <label>` counts a row with `count.py` and `form.py` (the typed form) and writes
`logs/count-<label>.txt`. Counts only; no rate was drawn.
