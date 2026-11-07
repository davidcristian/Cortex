# Readings: a forget by label and the recalls that restate the value

A forget whose text is a label or a phrase, such as `gym locker code`, finds the rows that contain
that text. A recall reply that restates the value in other words (`The code for your gym locker is
5819.`) does not contain it, so its row stays, and a later chat recalls the value after the reply
said it was forgotten ([ADR-0075](../adr/ADR-0075-forget-chosen-memories.md), decision 5).

## The flows

Each draw runs on the `cortexn15` stack over `Converse`, every card approved, each turn in a new
chat. Before a draw every `memories` row holding its value is deleted with `psql`.

| Turn | French draw (value `7731`) | English draw (value `5819`) |
| --- | --- | --- |
| a | `Souviens-toi que le code de mon casier à la piscine est 7731.` | `Remember that my gym locker code is 5819.` |
| b | `What is my swimming pool locker code?` | `What is the code for my locker at the gym?` |
| c | `Quel est le code de mon casier à la piscine ?` | `What number opens my gym locker?` |
| d | `Oublie le code de mon casier à la piscine.` | `Forget the code of my gym locker.` |
| e | `What is my swimming pool locker code?` | `What is my gym locker code?` |

The rows holding the value are counted before and after turn d.

A second English flow, `en-r`, forces the restated form: its turn c is `In one sentence that
starts with "The code for", what opens my gym locker?`, and its other turns are those above. It
was added before its draws, because none of the three English draws on the candidate restated the
value in other words.

## The pass rule

Written on 2026-11-07, before the draws on the candidate build. It is the rule of
[forget-chosen-memories.md](forget-chosen-memories.md#the-pass-rule) for these flows.

- A draw passes when the approved forget leaves no row holding the value, or its reply says how
  many remain, and the turn e reply does not contain the value.
- A forget that deletes a row its card did not list fails, whatever the other rows show.
- The change ships when no draw on the candidate fails the second item, and every draw whose card
  was approved passes the first. A draw whose model passed the value as the text reaches every
  row by the literal match on both builds, and is counted apart.

## The shipped build, 2026-11-07

One English draw on the stack brain built from `dfdf6b556`, the SM clock not read. The card of
`{"text": "gym locker code"}` listed the request and the reply `Your gym locker code is 5819.`;
the row of turn c, `The code for your gym locker is 5819.`, stayed. The reply said `I've forgotten
the code for your gym locker.`, and turn e answered `Your gym locker code is 5819.` It fails, as the
French flow of
[overlay-language-and-locale-flows.md](overlay-language-and-locale-flows.md#5-forget-in-other-languages)
did. So the defect is not a language gap.

## The candidate

When the text has a word of four or more letters, the card also lists every other row that holds
a value of a matched row as a whole token and a word of the text as a whole token. A value is a
token with at least four digits. The listed ids are what `invoke` deletes, so no row is deleted
unseen.

## The candidate draws, 2026-11-07

Eight draws on a second brain built from the candidate tree, sharing the stack's model host and
store, the SM clock at 0.57 of its maximum before and 0.72 after. Every card was approved.

| Draw | Text of the call | Rows listed by text, by value | Rows left | Turn e names the value | Result |
| --- | --- | --- | --- | --- | --- |
| fr1 | `code de mon casier à la piscine` | 2, 1 | 0 | no | pass |
| fr2 | `7731` | 3, 0 | 0 | no | pass, the value as text |
| fr3 | `code de mon casier à la piscine` | 2, 1 | 0 | no | pass |
| en1 | `gym locker code` | 3, 0 | 0 | no | pass |
| en2 | `gym locker` | 3, 0 | 0 | no | pass |
| en3 | `gym locker code` | 3, 0 | 0 | no | pass |
| en-r1 | `gym locker code` | 2, 1 | 0 | no | pass |
| en-r2 | `gym locker code` | 1, 2 | 0 | no | pass |

No forget deleted a row its card did not list, since `invoke` deletes the listed ids. Every draw
passes, so the change ships. The rows listed by value are the form the change fixes: they occur in
four of the seven draws whose text was a label or a phrase, and in two of five draws with the
unforced flows. In en1 to en3 every recall reply restated `gym locker code`, so the text alone
reached every row. A row holding the value with no word of the text is still left, and the result
does not say so
([task 1003](../refinements/tasks/1003-a-forget-reports-nothing-of-a-value-left-without-a-word-of-its-text.md)).

The first reply of fr1 was `C'est noté, je记下 (je retiens) que le code de votre casier à la
piscine est 7731.`, with a Chinese word, and that row was then listed on its card
([task 1004](../refinements/tasks/1004-a-french-reply-can-hold-a-chinese-word.md)).

## A value left with no word of the text: flow and rule, 2026-11-07

For [task 1003](../refinements/tasks/1003-a-forget-reports-nothing-of-a-value-left-without-a-word-of-its-text.md).
The `en-v` flow runs the English turns a, d and e above, and between a and d one recall that names
only the value: `Reply with only the number: which number did I ask you to keep?`. Its row holds
`5819` and no word of `gym locker code`, so the card does not list it.

Written before the baseline draws on the shipped build:

- A turn d reply passes when it does not say the code was forgotten, or says that a remembered
  exchange still holds it. The draws where a row holding the value is left after the forget are
  counted apart, as the form.
- A change to the result text ships when, over three draws, every draw showing the form passes,
  and no result the model reads names the value. The baseline is expected to fail every such draw.

## Baseline draws, 2026-11-07

Three `en-v` draws on the stack brain built from the commit that lists repeats, the SM clock at
0.57 of its maximum before and after. The form did not occur: turn b was answered `0` in two draws
and in the first ran to the length limit, its thinking repeating `Actually, I'll just say "None".`
for about 6,000 words, because recall returned an older memory and not the code
([task 1005](../refinements/tasks/1005-a-recall-question-that-finds-no-value-loops-in-its-thinking.md)).
So no row held `5819` beside the request row, each forget deleted that row, and each turn d reply
said the code was forgotten, which was true. The flow needs a turn b whose recall reaches the
code and whose reply names only the value; `What is my gym locker code? Answer with the number
only.` puts `gym locker code` in the row, so it does not serve either.

## The whole-value reader replayed, 2026-11-07

The flows above, replayed on the stack brain rebuilt from the commit that names an earlier delete
only for a later forget of that fact, every card approved, the SM clock at 0.57 of its maximum
before and 0.52 after. On this build a row is listed by value only when it holds a whole value of a
match (a phone number or code in full, never a part, a year, a date, a time or an amount), under
a line naming that value. The pass rule above applies unchanged.

| Draw | Text of the call | Rows listed by text, by value | Rows left | Turn e names the value | Result |
| --- | --- | --- | --- | --- | --- |
| fr1 | `code de mon casier à la piscine` | 2, 1 | 0 | no | pass |
| en1 | `gym locker` | 3, 0 | 0 | no | pass |
| fr2 | `code de mon casier à la piscine` | 2, 1 | 0 | no | pass |
| en2 | `gym locker code` | 3, 0 | 0 | no | pass |
| fr3 | `casier à la piscine` | 2, 0 | 1 | yes | fail, the form of task 1003 |
| en3 | `gym locker code` | 3, 0 | 0 | no | pass |
| en-r1 | `5819` | 3, 0 | 0 | no | pass, the value as text |
| en-r2 | `5819` | 3, 0 | 0 | no | pass, the value as text |

No forget deleted a row its card did not list. In fr3 the row left is the English recall `Your
swimming pool locker code is 7731.`, which holds neither `casier` nor `piscine`, so no word of the
text; the reader of the commit that lists repeats, run on the same three rows and text, lists
the same two. So fr3 is not a change of this build but the form of
[task 1003](../refinements/tasks/1003-a-forget-reports-nothing-of-a-value-left-without-a-word-of-its-text.md),
and its turn d reply said the code was forgotten. The run records are
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot13/draws-c.jsonl`
and `draws-r.jsonl` beside it.
