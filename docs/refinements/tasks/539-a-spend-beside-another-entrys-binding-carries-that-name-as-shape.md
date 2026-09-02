# A spend written beside another entry's binding carries that binding's name as shape

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a `crosscheck` fault over the kind word after a rename of a field binding sending a
reader to the wrong constant, or a third entry whose spend is written on a line beside another
entry's binding.
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

**What would close it.** Either a mention carrying a second name, rendered from another entry's
site so a rename there re-renders this needle rather than leaving it unfound, or a narrower spend
for the kind word, `: {name},`, that carries no neighbour's name and holds less. The mutation is
the one that showed it: rename `_KIND_FIELD` on the server together with its use and watch the
gate fault the field entry alone.

## Trail

- 2026-09-02: opened by the close of
  [537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md), recorded in its
  ADR-0029 declaration-fields addendum.
