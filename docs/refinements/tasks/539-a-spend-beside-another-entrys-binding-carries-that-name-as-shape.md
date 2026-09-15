# A spend written beside another entry's binding carries that binding's name as shape

**Status:** landed 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of
[537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md), whose fifth mutation
showed it.

A mention's template renders one `{name}` and one `{value}`, and everything else in it is shape.
The server's one line writing a declaration now spends four registered bindings,
`{_SOURCE_META_KEY: {_KIND_FIELD: _SENDER_KIND, _VALUE_FIELD: sender}}`, and the kind word's spend
is held as `_KIND_FIELD: _SENDER_KIND,` so that the word is held to the field it is written under.
That needle renders the kind word's name and carries the kind field's binding name as shape,
spelled in the registry from the same `KIND_FIELD` constant the field entry's sites read. Renaming
the field binding on the server, name and use together, faults the kind-field entry rightly
(`server.py declares no _KIND_FIELD`) and the kind-word entry beside it, whose message says the
whole of its needle is shape: a neighbour moved, and a constant that did not is named, which is
the misattribution the ADR-0023 bind-host addendum measured. Both faults are printed, the right
one second.

**Why it was left.** The registry has no way to say that part of one entry's shape is another
entry's name. Giving a template a second placeholder for a foreign name asks the registry to
relate entries, which nothing in `couplings.py` does today, and the fault is loud rather than
silent, since the right entry is named on the same run. One line spending four bindings is also
the only place this shape occurs.

**What it became.** Neither of the two remedies above, because the misattribution this entry is
about already had a remedy in the scan and it simply did not run here. `needles.unfound` gives an
unfound needle two readings and, where they name one line, says that what moved is likely shape and
that the constant named may not be the one to change. It took that reading only for a mention
rendering a value, answering a name-rendering one with `this needle renders no value, so the whole
of it is shape`, which is wrong about the needle in front of it: the rendered name is the one part
of it this constant answers for. `needles.answered` now says which half a needle's constant answers
for, the value where the template renders one and the name where it renders only a name, and the
verdict names whichever it read.

The needle still carries the field's binding name as shape and the registry still relates no
entries, which the fault now says out loud on the line the neighbour moved on. Both entries are
rendered from the one `KIND_FIELD` constant in `scripts/emailcouplings.py`, so one registry edit
repairs both faults; what was costing a reader was the sentence, and the sentence is the thing that
changed. Fifteen mentions render a name and no value today, so every one of them gained the
reading rather than the kind word alone.

## Trail

- 2026-09-02: opened by the close of
  [537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md), recorded in its
  ADR-0029 declaration-fields addendum.
- 2026-09-04: checked and left open. The trigger as first written counted "a third entry", which
  no reading of the registry produces, so it is restated as a second entry and made countable.
  Rendering all 288 mentions and searching each needle's literal shape for the site names the
  registry declares finds exactly one: the kind word's spend, `_KIND_FIELD: _SENDER_KIND,`. Two
  other hits are substring coincidences rather than instances, the compose default and the vision
  runbook row both carrying `MAX_IMAGE_BYTES` inside the env var name
  `CORTEX_BODY_MAX_IMAGE_BYTES`, which renaming that binding would not move. Nothing landed since
  the entry was opened changes the count: the one mention added in the meantime,
  `SHIPPED_BUDGET = Budget({value})` in the injection harness, spells the far file's own binding
  and no other entry's.
- 2026-09-09: measured again, and the one instance is unchanged: the server still writes
  `{_SOURCE_META_KEY: {_KIND_FIELD: _SENDER_KIND, _VALUE_FIELD: sender}}` on one line, and the
  kind word's spend is still the only needle whose literal shape carries a site name belonging to
  another entry. The two numbers beside it both moved. The registry renders 296 mentions rather
  than 288, and the coincidences number seven rather than two, because a site named `_IMAGE` was
  registered for the CUDA engine image and that name falls inside `CORTEX_IMAGE_MAX_TOKENS` and
  `CORTEX_BODY_MAX_IMAGE_BYTES`, which five further needles spell. A short site name matching
  inside a longer env var is what this measurement will keep turning up, so the count of
  coincidences is worth re-deriving rather than reading off the bullet above.
- 2026-09-14: measured again and the instance is still one. The server still writes
  `{_SOURCE_META_KEY: {_KIND_FIELD: _SENDER_KIND, _VALUE_FIELD: sender}}` on one line, and the
  kind word's spend, rendered `_KIND_FIELD: _SENDER_KIND,`, is the only needle whose literal shape
  carries a site name belonging to another entry. The registry is 92 constants over 96 site names
  and renders 313 mentions, up from 296, and the coincidences are still the seven `_IMAGE` hits
  inside `CORTEX_IMAGE_MAX_TOKENS` and `CORTEX_BODY_MAX_IMAGE_BYTES`. Searching each needle for
  every site name rather than only for foreign ones returns 29 hits, the extra 21 being mentions
  that spell their own entry's binding, which is the ordinary shape of a module-doc row and not
  what this entry counts.
- 2026-09-15: landed. The mutation this entry names was run first and reproduced exactly what it
  describes, two faults with the misleading one printed first. What it became is the reading above,
  recorded in the ADR-0029 addendum on a needle that renders a name, which carries both faults in
  full and the mutation table over `scripts/needles.py`. The instance is still one and the shape is
  worth counting again if a second entry ever spells another entry's site name in its needle: the
  fault it would cost is now a pointing one rather than a misleading one, so the count matters less
  than it did.
