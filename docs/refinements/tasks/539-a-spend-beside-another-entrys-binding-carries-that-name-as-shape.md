# A mention written beside another entry's binding includes that name as literal text

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

A mention's template writes one `{name}` and one `{value}`, and the rest of it is literal text. The
server's one line writing a declaration uses four registered bindings,
`{_SOURCE_META_KEY: {_KIND_FIELD: _SENDER_KIND, _VALUE_FIELD: sender}}`, and the kind word's mention
is `_KIND_FIELD: _SENDER_KIND,`, so the word is compared against the field it is written under. That
search text writes the kind word's name and includes the kind field's binding name as literal text,
taken in the registry from the same `KIND_FIELD` constant the field entry declares. Renaming the
field binding on the server, name and use together, fails the kind-field entry correctly
(`server.py declares no _KIND_FIELD`) and the kind-word entry beside it, whose message said the
whole of its search text was literal: a neighbour moved, and a constant that did not is named, which
is the wrong attribution ADR-0042 decision 25 describes. Both failures print, the correct one
second.

**Why it was left.** The registry has no way to say that part of one entry's literal text is another
entry's name. Giving a template a second placeholder for a foreign name asks the registry to relate
entries, which nothing in `couplings.py` does today, and the failure is visible rather than silent,
since the correct entry is named on the same run. One line using four bindings is also the only
place this happens.

**What it became.** Neither remedy above. The scan already had a remedy for this wrong attribution
and it did not run here. `searchtexts.unfound` gives an unfound search text two readings and, where
they name one line, says that the form probably changed and the constant it named may not be the one
to change. It took that reading only for a mention writing a value, and answered a name-writing one
by saying the whole search text was literal, which is wrong about it: the written name is the one
part this constant is responsible for. `searchtexts.answered` now says which half a search text's
constant is responsible for, the value where the template writes one and the name where it writes
only a name, and the result names whichever it read. The search text still includes the field's
binding name and the registry still relates no entries, which the failure message now states on the
line the neighbour moved on. Both entries are written from the one `KIND_FIELD` constant in
`scripts/emailcouplings.py`, so one registry edit repairs both failures. Fifteen mentions write a
name and no value today, so every one of them gained the reading.

## History

- 2026-09-02: opened by the close of
  [537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md), recorded in ADR-0042.
- 2026-09-04: checked and left open. The trigger as first written counted "a third entry", which no
  reading of the registry produces, so it was restated as a second entry and made countable. Writing
  all 288 mentions and searching each search text for the declaration names the registry has finds
  exactly one, the kind word's mention `_KIND_FIELD: _SENDER_KIND,`. Two other hits are substring
  coincidences: the compose default and the vision runbook row both contain `MAX_IMAGE_BYTES` inside
  the variable name `CORTEX_BODY_MAX_IMAGE_BYTES`, which renaming that binding would not move.
- 2026-09-09: measured again, and the one instance is unchanged. Both numbers beside it moved: the
  registry writes 296 mentions rather than 288, and the coincidences number seven rather than two,
  because a declaration named `_IMAGE` was registered for the CUDA engine image and that name falls
  inside `CORTEX_IMAGE_MAX_TOKENS` and `CORTEX_BODY_MAX_IMAGE_BYTES`, which five further search
  texts contain. A short declaration name matching inside a longer variable name is what this
  measurement keeps turning up, so count the coincidences again rather than reading the number off
  this line.
- 2026-09-14: measured again and the instance is still one. The registry is 92 constants over 96
  declaration names and writes 313 mentions, up from 296, and the coincidences are still the seven
  `_IMAGE` hits. Searching each search text for every declaration name rather than only foreign ones
  returns 29 hits, the extra 21 being mentions that contain their own entry's binding, which is the
  ordinary form of a module-doc row.
- 2026-09-15: done. The mutation this entry names was run first and reproduced two failures with the
  misleading one printed first. The fix is the reading above, recorded in ADR-0042, with both
  failures tabled over `scripts/searchtexts.py`. The instance is still one, and a second one would
  now cost a pointing failure rather than a misleading one.
