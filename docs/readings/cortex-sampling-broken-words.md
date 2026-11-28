# Readings: broken words in Romanian reminder replies at two cortex sampling settings

Whether a lower temperature or a higher `min_p`, sent in each cortex request, cuts the broken words
in the cortex's replies to three Romanian reminder messages and in the items it stores. The task
is [R-1057](../refinements/tasks/1057-a-romanian-reminder-reply-holds-a-broken-word.md); the
count at the server's own sampling on 2026-11-23 is in
[single-draw-recounts.md](single-draw-recounts.md#a-romanian-reminder-reply-with-a-broken-word).
The stack sends no sampler today ([ADR-0077](../adr/ADR-0077-model-card-settings.md) decision 1).

## The stack, 2026-11-25

The brain was built from the tree at `b67667c0a` and run on its compose defaults with the memory
override, schedules on (`CORTEX_SCHEDULE_BACKEND=redis`, zone `Europe/Berlin`), escalation off and
no tool sidecar. The model host ran from the `cortex-model-host` image, engine build
`b12375-9d25e0014`, with the tree's model manager bound over the image's. Its argv for the cortex,
after the model path `unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`:
`-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192 --model-draft
.../mtp-gemma-4-12B-it-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3`. So the KV cache is
the engine's f16, the drafter is the multi-token-prediction file at draft length 3, and no
reasoning effort is set.

`/props` reads temperature 1.0, `top_k` 64, `top_p` 0.95, `min_p` 0.05, repeat penalty 1.0, DRY
and XTC off, and the sampler order `penalties, dry, top_n_sigma, top_k, typ_p, top_p, min_p, xtc,
temperature`. So `min_p` drops tokens before the temperature scales the rest.

A recording proxy between the brain and the cortex merged one JSON object into every request that
has a `messages` list: the turn's requests, the recall judge's and the title's. The first turn
request of tonight equals the 2026-11-23 one once times and ids are masked, in its messages and its
tool list, and holds no sampling field in the base cell.

## The rule, written before the first draw

Three cells of the 24 messages of 2026-11-23, M1 `Amintește-mi la ora 18 să scot gunoiul pentru
colectarea de luni.`, M2 `Amintește-mi mâine la ora 9 să sun la dentist.` and M3 `Amintește-mi
vineri la ora 17 să plătesc factura la curent.`, eight draws each, a new chat each, with the store
and the schedule items emptied before each draw and every card approved:

- **base**: no field, so the server's settings above.
- **T**: `"temperature": 0.5` in every cortex request.
- **M**: `"min_p": 0.2` in every cortex request.

Counted by reading, as on 2026-11-23: a reply holding a word that is not Romanian, with a loanword
counted apart and a name, number, time, date or appended note not counted as words; the stored
item's text read the same way. A Romanian word in the wrong sense or form is also counted apart.
Counted from the requests: draws calling `schedule_task` exactly once, and draws calling
`forget_memories`.

- A cell is **supported** when it reads at most 2 of 24 replies and 0 of 24 items with a broken
  word, base reads at least 5 of 24 replies, and the cell calls `schedule_task` once in no fewer
  draws than base less one.
- No default or prompt changes on these rows, whatever they read: a sampler the brain sends
  reaches every cortex request, so it can move every cortex row the repo keeps (the list below),
  and none of those is redrawn here. A supported cell is recorded with a task to redraw them.

Base read 4 of 24, under its bound of 5. A second set of all three cells was then written, before
any T or M row was read, and judged on the 48 draws of each cell pooled: supported at most 4 of 48
replies and 0 of 48 items, with base at least 10 of 48 and the cell's single calls no fewer than
base's less two.

## The draws

| cell | set | replies with a word that is not Romanian | items with one | wrong sense or form | loanword `reminder` | `schedule_task` once |
| --- | --- | --- | --- | --- | --- | --- |
| base | 1 | 4 of 24 | 1 of 24 | 3 | 2 | 23 of 24 |
| base | 2 | 2 of 24 | 3 of 24 | 1 | 1 | 21 of 24 |
| T | 1 | 3 of 24 | 3 of 24 | 1 | 2 | 22 of 24 |
| T | 2 | 0 of 24 | 1 of 24 | 2 | 1 | 21 of 24 |
| M | 1 | 0 of 24 | 3 of 24 | 2 | 3 | 22 of 24 |
| M | 2 | 3 of 24 | 3 of 24 | 3 | 2 | 22 of 24 |
| base | pooled | 6 of 48 | 4 of 48 | 4 | 3 | 44 of 48 |
| T | pooled | 3 of 48 | 4 of 48 | 3 | 3 | 43 of 48 |
| M | pooled | 3 of 48 | 6 of 48 | 5 | 5 | 44 of 48 |

**No cell is supported**, by either rule: base read under its bound both times, and every cell
stored items with a broken word. This is the null result.

- The words that are not Romanian: `Scote` and `Scoat` for `Scoate` (take out), `o reaminte`,
  `amânteala`, `hatırlatıcı` (Turkish), and `programatख nhắc nhở` (a Devanagari letter and
  Vietnamese). `hatırlatıcı` and `Scote` each appeared in replies of every cell.
- The items: every broken item is M1's `Scote` or `Scoat`, the cortex's own wording in the call's
  `text` argument, which the person reads when the reminder fires. Neither setting removed it.
- The wrong sense or form: `amânarea` (the postponement), `întârziere` (a delay), `o reamintește`
  and `amintea` (verb forms for the noun).
- Every draw but one stored one item at the hour asked. The one asked which day the person meant
  (base, second set, M1), since the draws ran on a Wednesday and M1 names Monday's collection. M1
  read as Monday in 12 of its 48 draws over all cells and as today in 35. On 2026-11-23, a Monday,
  the two readings were the same day.
- Every draw that called `schedule_task` twice was the weekly check's refusal of `on_days` for one
  named weekday, then the one-day call, a shipped path
  ([schedule-one-time-weekday.md](schedule-one-time-weekday.md)). Six M1 items were stored as
  daily, and each reply said so, in the cortex's own words or the brain's note; one more was made
  one time with `edit_scheduled` after the daily result. No draw called `forget_memories`.
- Median trace characters over the 48 draws: base 1,637, T 1,971, M 1,404.

## The rows a cortex sampler can move

Each of these was drawn at the server's own settings and would need drawing again under a sent
sampler before it changed: the store-tool search and the `forget_memories` calls on requests to
remember ([remember-request-tool-search.md](remember-request-tool-search.md),
[single-draw-recounts.md](single-draw-recounts.md),
[side-effect-tools-on-remember.md](side-effect-tools-on-remember.md)); the forget card and
refusal rows (`forget-*.md`); the injection rows the cortex is the boundary for; the schedule rows
(`schedule-*.md`); the language and locale flows
([overlay-language-and-locale-flows.md](overlay-language-and-locale-flows.md)); and the recall
judge's orders.

Method: `all.sh`, `draw1057.sh` and the proxy in `proxy/` draw; `count1057.py <cell>` reads each
cell, and the hand reading of every draw is `logs/hand1057.md`; all in
`~/.cache/cortex-run/2026-11-25/s1/`, with the rows in `logs/r1057-<cell>.jsonl` and the items in
`logs/r1057-<cell>-items.txt`. The project was removed after the draws.

## A typed check of the item, replayed 2026-11-27

The rule, written before the replay. Fold case and the Romanian diacritics (`ă` and `â` to `a`,
`î` to `i`, `ș` to `s`, `ț` to `t`). An item word passes when it equals a word of the message, or
when it is the third person singular or the imperative of a first person singular verb of the
message: `-esc` becomes `-este`, `-ez` becomes `-eaza`, and a stem ending in a consonant takes `-a`
or `-e`, its last vowel `o` becoming `oa` (`scot` to `scoate`). An item is flagged when one of its
words does not pass. The near misses read as written: `Scot`, `Scoate`, `Să scot`, `Sună`, `Suna`
and `Plătește` pass, `Scote` and `Scoat` are flagged. The check is built only when no right item
is flagged.

The replay covers all 167 items stored by the draws above and those of 2026-11-23: 24 from
2026-11-23 and 143 from 2026-11-25, where one draw asked a question and stored none.

| item text | items | flagged | right |
| --- | --- | --- | --- |
| `Scote gunoiul pentru colectarea de luni` | 17 | yes | no |
| `Scoat gunoiul pentru colectarea de luni` | 1 | yes | no |
| `Să scoți gunoiul pentru colectarea de luni` | 1 | yes | yes |
| the other 12 texts | 148 | no | yes |

The rule flags all 18 broken items and 1 right one: `Să scoți` (that you take out), a second
person form, from the base cell's fourth M1 draw on 2026-11-25. So the check is not built.

The replies, counted over the same 168 draws: 20 hold a word that is not Romanian, 8 on 2026-11-23
and 12 on 2026-11-25. 8 of them quote the item's `Scote` or `Scoat`, and 6 of those 8 hold no
other such word. The other 14 hold the cortex's own word for a reminder (`hatırlatıcı`,
`amânterea`, `o reaminte`), which neither the item nor the message holds. A search for a letter
outside the Romanian alphabet finds 6 of the 168 replies, all among those 14, and no right reply;
the other 8 are written in Romanian letters.

Method: `items.py` reads the items, `check.py` replays the rule, and `replies.py` and `letters.py`
count the replies, with their logs, in `~/.cache/cortex-run/2026-11-27/c5/`.

## A letter check of the reply, the rule written 2026-11-28

The rule, written before the replay and the generated sentences. The check reads the model's text
of a turn whose every tool call is `schedule_task` and at least one stored an item, so the only
tool results are creation results, which name an id, a kind and a due time and never a word of
the item.

- **The language** is the one the note pick (`message_language`) reads for the message. When no
  language leads, the pick falls back to English and the check does not run, since the message's
  alphabet is not known.
- **The alphabets.** Every language holds the 26 letters `a` to `z`. French adds `à â æ ç é è ê
  ë î ï ô œ ù û ü ÿ`, German `ä ö ü ß`, Spanish `á é í ñ ó ú ü ª º` and Romanian `ă â î ș ş ț ţ`.
  English holds all of those, since English writes words such as `café` and `naïve`. Case is
  folded before a letter is read.
- **A word** is a run of characters between white space, less the punctuation at its two ends.
  A word is **marked** when it holds a letter outside the alphabet and none of these holds: the
  message or a stored item's text holds the word (case folded); its first letter is a capital,
  which reads as a name; it holds a digit, which reads as a number; it stands between backticks,
  which reads as code. Emoji and other symbols are not letters.
- A reply is marked when one of its words is.

Acceptance, all three needed before a note is built on the check: all 6 recorded replies holding
a letter outside the Romanian alphabet marked; 0 of the 162 other recorded replies marked; and 0
of at least 2,000 true reminder replies marked, generated in English, French, German, Spanish and
Romanian from each message's own words, with names and quoted text from other scripts (Cyrillic,
Greek, Turkish, Polish, Czech, Vietnamese, Devanagari, Chinese, Arabic) mixed into the message
and quoted by the reply.

### The replay and the generated replies

| set | replies | marked | wanted |
| --- | --- | --- | --- |
| recorded, a letter outside the Romanian alphabet | 6 | 5 | 6 |
| recorded, the others | 162 | 0 | 0 |
| generated true replies, 3,456 per language | 17,280 | 0 | 0 |

**The rule fails**: it marks 5 of the 6. The sixth, `Am setat o hatırlatıcı` in the second base
set's first M1 draw, called `edit_scheduled` after `schedule_task`, so its turn is not checked;
the letters alone mark it. The other unchecked turn asked a question and stored nothing. So no
note is built on this rule. The turn condition is there for the note: an edit can change the
text and the due time a creation result named, so a note restating the creation would be false
on such a turn.

The generated replies cover 4 tasks, 3 messages and 8 replies per language at 3 hours, each task
holding one of 12 names from other scripts (`Дмитрий`, `Γιώργος`, `Çağrı`, `Łukasz`, `Dvořák`,
`Nguyễn`, `राहुल`, `王伟`, `محمد`, `Søren`, `Zoë`, `Ольга`) and, in two of the 4, a quote from
another script. Replies quote the item, restate the task in the message's words, and add the
language's own words, emoji, a code span and an ordinal. The note pick reads 48 of the 3,456
Spanish messages as English: the quoted Danish `tak for i går` holds two words the English list
counts. A planted broken word in 2 of the 8 Romanian replies is marked in all 864 of them; the
same word opening a sentence (`Przypomínání programat`) is not, since a capital reads as a name.

Method: `replay.py`, `gen.py` and `gen_broken.py` with the rule in `letters_rule.py` and their
logs, in `~/.cache/cortex-run/2026-11-28/c2/`.
