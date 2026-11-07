# Readings: a later round that repeats an earlier sentence in other words

How often a second round of the tool loop, after `OpeningHold` (`round_opening.py`) has dropped
what it repeats word for word, still opens by saying again what the first round said, and in which
words. The earlier rows and the hold's rules are in
[reply-repeat-across-a-tool-call.md](reply-repeat-across-a-tool-call.md).

## Rows and rule, 2026-11-07

Written before any draw, for
[R-979](../refinements/tasks/979-the-other-rewordings-of-a-repeated-sentence-are-not-recorded.md).

The rig is the `cortexn15` stack's cortex (gemma-4-12B text only, llama-server build
`b12169-3ed7284f2`, context 16384). A second brain built from the tree, whose brain was last
changed by the commit that names an earlier delete when a later forget matches nothing, sent its
requests through a recording proxy. One W04 draw over `Converse` called `forget_memories` with
`{"text": "0612345678"}` and no text before the call, and the proxy recorded its second-round
request: the system message, the 19 tools, W04's message, the call and its result, with `stream`
and no sampling field. Each draw sends that request directly to the server with two changes, as
A4 did:

- the call message's `content` is A2's first round: `The capital of Australia is Canberra. I have
  also removed the phone number 0612345678 from my memory as you requested.`
- the result is `forgot 1 remembered exchanges; no remembered exchange contains that text now.`
  and the note the dispatcher adds to every `forget_memories` result today.

`stream` is false and `max_tokens` is 1500, as a limit on the rig. Row A5 is 20 draws.

Each second round is fed to today's `OpeningHold`, built on the first round's text, in pieces of 1
to 5 characters from a fixed seed, and then flushed. What the hold streams is the round's `shown`
text. The second sentence means the first round's sentence about the phone number. Each round is
counted as:

- `opens`: its text begins, after white space, with a sentence the first round holds word for word.
- `restates`: the first sentence of `shown`, split as the hold splits, has `0612345678`, `phone
  number` or `number`, or a form of `forget`, `remove`, `delete` or `erase`. Each such sentence is
  listed with the words in which it differs from the second sentence.
- `kept`: a sentence of `shown` after its first one meets the same test.
- `empty`: it has no text and no call. `recall`: it calls a tool again.

The rule for a change of the hold:

- **What may change.** The hold may read two sentences as the same only by rewrites that change no
  fact, from this closed list: a contraction and its long form (`I've` and `I have`, `I'm` and `I
  am`, `it's` and `it is`, `that's` and `that is`), and the words `also`, `now`, `just`,
  `successfully`, `too` and `as well`. A rewrite outside the list, such as a verb for another
  (`deleted` for `removed`), a number left out, `your` for `the`, or a changed word order, is not
  admissible, and the list is recorded with what it would need.
- **The fix ships** when a restating sentence of A5 differs from the second sentence only by the
  list's rewrites and the closing `as you requested` the hold already reads, and a new hold that
  applies those rewrites, with the near misses written as tests before its code, passes three
  checks: every near miss of today's tests and the new ones is kept; replaying every A5 round
  through the old and new hold, the new one drops each restating sentence the list covers; and it
  changes no round in which the old hold shows no restating sentence. The near misses: the same
  sentence with a number, a name or an ending that differs, an added fact, a question, a negation,
  and a listed word that stands before a new fact (`I also removed the address.`).
- **How often the form occurs** is a separate count, `covered`, of the restating rounds the list
  covers. It does not decide whether the fix ships.
- **No change.** When no restating sentence is covered, the hold stays as it is and the task
  closes with the list.

Row A6 was written after A5's draws and before any of its own, because A5 has one restating round
and so names one form: 60 more draws of the same request, read with the same counts and rule as A5,
over A5 and A6 together.

## The draws, 2026-11-07

Run logs `a5.jsonl` and `a6.jsonl`, the recorded request `second.json`, and the scripts `draw.py`,
`replay.py` and `compare.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot3/`.
The SM clock read 0.57 of its maximum before each row and 0.67 after it.

| Row | Draws | `opens` | `restates` | `kept` | `empty` | `recall` |
| --- | --- | --- | --- | --- | --- | --- |
| A5 | 20 | 20 | 1 | 0 | 0 | 0 |
| A6 | 60 | 59 | 2 | 0 | 0 | 0 |

76 of the 80 second rounds write both of the first round's sentences again and nothing else: 70 word
for word, 4 ending `as requested` and 2 with no closing, which the hold already reads as the same.
The 80th writes only `Is there anything else I can help you with?`. The 3 restating sentences, with
the words in which each differs from `I have also removed the phone number 0612345678 from my memory
as you requested.`:

| Draw | Sentence the hold shows | Differs by | On the list |
| --- | --- | --- | --- |
| A5 10 | `I've also forgotten the phone number 0612345678 as you requested.` | `I've`; `forgotten` for `removed`; `from my memory` left out | no |
| A6 14 | `I've also removed the phone number 0612345678 from my memory as you requested.` | `I've` | yes |
| A6 28 | `I've also forgotten your phone number as requested.` | `I've`; `forgotten` for `removed`; `your` for `the`; the number and `from my memory` left out | no |

So `covered` is 1 of 3, and the fix ships. `OpeningHold` now reads `I've`, `I'm`, `it's` and
`that's`, and the same with a curly apostrophe, as `I have`, `I am`, `it is` and `that is`. The
list's words (`also`, `now`, `just`, `successfully`, `too`, `as well`) are needed by no restating
sentence, so the hold does not read them. Its new tests keep every near miss: a changed number or
ending, an added fact, another verb, a number left out, `had` or `I'd` for `have`, a lower case
`i've`, a question, a negation, `also` before a new fact and `its` against `it's`.

Replaying all 80 rounds in pieces of 1 to 5 characters through the old and new hold, the new one
changes only A6 14, which it drops whole, so `restates` falls from 3 of 80 to 2. The other 2 stay:
a number left out is the near miss `I have also removed the phone number.` that the hold's tests
keep, and a verb for another is outside the list. Over the 99,249 distinct sentences of the
readings, task files and brain tests, the new reading changes 245 and reads 2 pairs as one that the
old one read as two, each a sentence and its own contracted form.

## A live row on the new hold: rows, 2026-11-07

Written after the fix was committed and before any draw of its own. The stack brain, rebuilt from
the tree with the new hold, draws W04 15 times over `Converse` with every card approved, `memories`
cleared of the draw's rows after each. The driver splits each reply's text at its `tool_activity`
events. It counts the calling draws, those with text before the call, and the replies in which a
round after the first opens with a sentence an earlier round wrote, as the new hold reads them. It
checks that the change broke nothing live and decides nothing.

## A live row on the new hold: result, 2026-11-07

Run log `live.jsonl` and the driver `turn_rounds.py` in the same directory as the draws, the SM
clock at 0.57 of its maximum before the draws and 0.68 after them. Of the 15 draws, 11 call
`forget_memories` and 3 of those write text before the call, which each reply shows. No later round
opens with a sentence an earlier round wrote. In one of the 3 the first round ends `I have also
removed your phone number 0612345678 from my memory.` and the second round is `I have also removed
your phone number from my memory as requested.`: the form with the number left out, which the hold
keeps. In the other 2, the round after the call writes a new sentence. The brain's note for a forget
that deleted nothing ends both replies that claim a removal, since `memories` held no phone row.
