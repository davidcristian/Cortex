# ADR-0042: The cross-tree constant registry

**Status:** Accepted (2026-09-19)

## Context

Screen capture ([ADR-0029](ADR-0029-vision-screen-capture.md)) has one byte ceiling enforced in two
places: `MAX_CAPTURE_BYTES` in the Rust body and `MAX_IMAGE_BYTES` in the Python brain. Each
toolchain could assert its own copy, but such an assertion compares a tree with itself: changing a
constant and its own assertion leaves both suites green while the two trees disagree, which was
measured before anything here was built. The same pattern recurs across the repo. A port is declared
in Rust and in Python, a default declared in Python is restated in a compose file, a runbook's table
and a module contract, and the overlay's TypeScript and its stylesheet each write a duration.

The registry began as the comparison for that one ceiling and grew into the repo's general answer
for a value written in more than one place. Its decisions were taken under ADR-0029 over several
weeks and moved here to keep each record to one subject.

## Decision

### The registry and its comparison

1. **A registry of linked values, not a check of one pair.** `scripts/crosscheck.py` runs in
   `just check` and in CI's unconditional cross-tree job. Each entry is a `Constant`: a label, a
   reason printed with any fault, its declaring `Site`s (path and identifier) and its `Mention`s,
   two places at least. The gRPC token's metadata key was the second entry, with three hand-written
   sites, which showed the pattern generalizes past a pair.
2. **There is no master copy.** Sites are compared with each other, never against a value in the
   registry, and the comparison is symmetric. A designated original would leave one file editable
   alone, and the proto cannot be a master because it declares no constants.
3. **Fail closed.** A missing, unreadable or non-UTF-8 file, an unknown suffix, an absent name, a
   name declared twice, a value that cannot be reduced, and an entry naming fewer than `MIN_PLACES`
   places all exit with status 1. The suite runs the registry against the real tree and refuses an
   entry whose places all sit in one language, or in one language inside one brain package, since
   the email sidecar and the brain cannot import each other by design. A copy reachable by an import
   is imported rather than registered: what can be imported decides, not importance.

### What a value is

4. **Six forms reduce; anything else is refused.** A product of integer literals (optionally
   opening with a minus), a double-quoted string, a parenthesized run of such strings reduced to
   the string Python joins, a one-line `frozenset` of strings compared as a set, a decimal reduced
   to `values.Digits` (its written digits, so `5` and `5.0` are two forms), and a boolean reduced to
   `values.Truth` (its word). A guessed reduction would report two values as equal that were never
   compared. `crosscheck.DECLARATIONS` holds one declaration syntax per language: module-level
   Python, Rust `const` or `static`, and TypeScript `const` at column 0. A site names what a file
   declares, so a private `_NAME` is read under its underscore; the scan imports nothing.
5. **Three relations.** `EQUAL` by default. `ORDERED` requires sites to be non-decreasing in
   registry order and compares integers only, refusing a string, a decimal or a boolean. `MEMBER`
   requires every site but the last to hold a value that the last site's collection contains, and
   takes no mentions.

### Mentions

6. **A mention is a use, not a declaration**: a file plus a template the scan renders with the
   agreed value (`{value}`), the name the other side uses for it (`{name}`), or both, and then
   requires in that file. It covers compose strings, CSS `var()` reads, runbook table cells and bare
   literals. A mention includes a name exactly when its template renders one, and a name registered
   as a use requires a mention of the same entry rendering a value under it.
7. **Rendered search text is bounded, not counted.** `searchtexts.bounded` guards whichever edge is
   itself a word character, and a digit edge also refuses a neighbouring point and digit, so `5005`
   inside `50051` and `2048` inside `2048.5` are not found while `1..6291456` is. Search text
   contains the whole of what it checks and fits on one line. Position can matter: text
   anchored at the start of a line distinguishes a recipe line from a table cell.
8. **A count is exact and opt-in.** `Mention.occurrences` fixes how many times the search text
   appears in its file, never a minimum, because a minimum cannot report that it has gone stale;
   unset means presence.
9. **A mention may write the value differently.** `Form.WRITTEN` is the default, `WHOLE` renders
   a value with no fractional part (a non-zero fraction is a fault), `LOWERED` renders a boolean in
   lower case. An entry whose mentions all lose information this way needs one mention beside them
   that renders the value as written. A compose default is written as the constant's own text
   (`10.0`, not `10`) rather than registered with `WHOLE`, which is only for a syntax that refuses
   the site's text.
10. **A second form on a checked line gets its own mention.** There is no line-level or within-line
    occurrence mechanism, because it would manufacture links the next decision rejects.

### What counts as a second place

11. **The tense test.** A restatement is a second place when the value moving makes it wrong, and
    history when the value moving makes it a record of the past. Second places: an environment
    table's Default cell, a copyable recipe line, a module contract's stated default, the declaring
    file's own prose, a compose comment naming its own file's default, a sentence calling the number
    the shipped one, and a `docs/host/` instruction (a live instruction, not a record). History: an
    ADR, a readings record, a measured condition, a cost measured at a value, the ADR catalogue's
    summary of an ADR. A sentence naming the value as what a component returns is a second place
    even when a score sits beside it.
12. **Suites, by when they run.** A suite states what it asserts, so an assertion is not registered;
    a comment in a suite that no assertion reaches is a second place. A suite CI runs catches its
    own changes, so its fixtures stay out; an `integration`-marked or `#[ignore]`d suite that falls
    back to a shipped default is a second place, since it runs only when someone chooses to measure
    and a retune would leave it dialling a port nothing listens on. A wiring test that sets a value
    and reads it back is a fixture, since any value passes it.
13. **What is not a link.** A literal derived from a value (a height computed from an edge) is a
    consequence the language checks: `capture_bytes.rs` computes its expected size. Arithmetic
    around a value ("twice the 1800 s") stays out. A compose default no tree declares is not a link
    ([ADR-0063](ADR-0063-compose-checks.md)'s `defaultcheck.py` covers those), and an empty default
    means "not configured". A document describing the registry, `docs/modules/repo-checks-scans.md`,
    is not a second place.
14. **Defaults are moved out of the field.** A value defaulted inside `Field(...)` moves to a module
    constant beside the field, so it has a declaration to link and says which number a composed
    deployment runs.
15. **Search by name, never by digits.** Finding the other places is a method, not a scan: search
    for the name a value is declared under, and read each hit against the tense test. Two constants
    can share a number (`DEFAULT_SPILL_DWELL_S` and `DEFAULT_ADMISSION_WAIT_S` are both 3600).

### Structure

16. **Data in parts, logic in one scan.** `couplings.py` is the vocabulary (`Constant`, `Site`,
    `Mention`, `Relation`, `Form`); `values.py` reduces; `readings.py` says whether a set of
    readings is consistent; `searchtexts.py` and `linereadings.py` search and explain. Entries live
    in parts, each a `<subject>couplings.py` holding `<SUBJECT>_COUPLINGS`, added either by
    splitting at the line cap or as a new subject. `registry.py` is the one module naming them, and
    `CONSTANTS` is the parts joined in fault-report order and holds nothing of its own. The scan
    never asks which part an entry is in. The filing question between the gRPC and shipped parts is
    whether the other side's own code has to hold the value. A new part is named in `registry.py`'s
    docstring, the module contract's part list, its no-CLI list and the repo map.
17. **The suite checks the structure both ways.** The parts on disk are exactly what the registry
    reads; `registry.py`'s docstring lists every part in read order; no label appears twice; every
    `Relation` member is exercised; no two entries declare one set of sites; and of two `EQUAL`
    entries whose sites differ, one whose sites and mentions are both contained in the other's is
    reported as a copy. Orderings and memberships read sites by position, so containment is not
    applied to them.

### What a fault says

18. **Search text that is not found names what moved, when it can.** `searchtexts.nearest` picks the
    pair of the value's text nearest where the matched run stops and the run stop nearest that text,
    and reports both with their line, a quote windowed to `linereadings.QUOTED_WIDTH` and how many
    places write the value. `searchtexts.verdict` concludes that the surrounding text moved (`MET`)
    only when the value sits on the line the run stops on, and otherwise reports both readings
    (`APART`). `searchtexts.answered` says which half the constant is responsible for, the value or
    the mention's name, so a template rendering only a name is read on that name.

### A passing scan states what it covered

19. **Every cross-tree scan's success line states the size of what it checked**, as a reading and
    never an assertion: `crosscheck` prints entries, declaring sites, mentions and mentions with an
    exact count (`registry.shape`), and the other scans print their files, lines, binds, variables,
    servers, rosters or samples after every exclusion (`backlogcheck` prints its task counts on the
    lines before its result). A result that would be equally true of an empty tree then says what it
    was over. Nothing asserts the numbers, since a document is not a second place for a count; each
    scan's suite asserts that every count counts a different thing, over fixtures where no two
    coincide.
20. **A walk that measured nothing fails.** `linecap.py` and `dashcheck.py` exit 2 when they read no
    file, as `composefiles.py` already did for the compose scans; deeper counts get no minimum,
    since a compose file with no bind is ordinary. Suites set a minimum for their own walk where a
    middle value is known (`test_flagcheck.py`, `test_volumecheck.py` and others), and
    `settingscheck.MIN_CLASSES` sets one for the settings walk.

### Where a scan was declined

21. **No census of unregistered copies.** Uncovered occurrences of registered values run to tens of
    thousands and almost none are second places ([reading](../readings/constant-registry.md)), so a
    census check or report would be noise; decision 15 is the method instead.
22. **Log identity lines are a convention.** A scan over every `extra=` for identity-shaped keys is
    declined on its rate of false reports. `cortex_core/log_fields.py` and the brain-core contract
    state the rule: the registry covers the modules it lists, and a module that starts naming one of
    the five identity fields is registered in the same change.

### What a fault says about a line

23. **The matched run is read per line, from both ends of the search text.** `linereadings.py`
    credits each line with the search text's longest opening run and then the longest closing run
    after it, over the characters the opening left, after blanking the occurrences the file does
    hold; the line with the largest total is named only when it matches at least half the search
    text, and only as the line matching the most of it, never as where the text moved, because a
    deleted line leaves a sibling as the best. An opening run alone cannot find a change at the
    start of the search text (a compose publish whose interface changed). Search text containing a
    newline keeps the whole-file opening run. Measured over the registry's single-line search texts,
    reading from both ends names the changed line in 94% to 95% of single-character changes
    ([reading](../readings/constant-registry.md#which-line-a-fault-names)).
24. **A count never withholds the reading.** A file holding none of a counted search text gets the
    not-found reading, then the expected count as its own clause; a wrong count names the lines it
    found, and a short one also gets the per-line reading over what they leave. Both end on
    `crosscheck.RECOUNT`.

### A value inside another entry's search text

25. **A value inside another entry's search text is hidden, not checked.** Search text often
    contains other values (`127.0.0.1` inside the gRPC port's search texts is five different values:
    two bind defaults, a client default, the compose publish's host interface, and a loopback dial).
    That comparison is against the registry's own text, fails in one direction only, and names the
    wrong constant, so it is neither a link nor evidence the value is checked. A value is checked by
    its own entry, whose search text contains only its own value where the surrounding text allows.

## Consequences

- The registry covers, among others: the capture ceiling, edge, byte budget and deadlines; the gRPC
  token, port and endpoints; the model host's image budget and reasoning-off budget; the subagent
  tier's budgets and the bounds of a delegated run; the email sidecar's wire words and shipped
  answers; the mailbox names of the IMAP fixture; the five log field names; the overlay's durations,
  easing and custom properties against its stylesheet. Each part's docstring says what it covers.
- A retune is one edit per place that states the value, and the scan names every place that did
  not move. A value measured against, rather than shipped, still links its fixture when the suite
  using it never runs in CI.
- Known limits, each recorded under `docs/refinements/tasks/`: a narrower copy of an ordering or a
  membership passes; a mistyped use of a presence-checked name passes; search text may contain
  another entry's name; class-level declarations, collections outside Python, and multi-line sets do
  not reduce; a not-found reading over an ordinary word reads unrelated prose.
- Every registered number now has a declaration somewhere, which is itself a constraint on how a
  default is written (decision 14).

## Alternatives rejected

- **Per-toolchain assertions**: each compares a tree with itself.
- **Proto or one designated site as master**: leaves the master editable alone; proto holds no
  constants.
- **A minimum on mention counts**: cannot report that it has gone stale.
- **A part count in the success line, or faults attributed to a part**: the scan would learn the
  registry's layout; one grep finds a label's part.
- **A census check or survey report**: see decision 21.
- **Occurrence counting per line**: manufactures links the tense test rejects.
- **A unit-aware value form, or float comparison**: the comparison is textual by design.
- **Publishing CSS values at runtime with `setProperty`**: a `var()` resolving to nothing drops its
  declaration silently.
- **A quote-based rule for which half of the search text moved**: wrong in compose and markdown.

## Related

- The [repo checks module doc](../modules/repo-checks.md): the scan's contract and the method for
  finding a value's other places.
- Code: `scripts/crosscheck.py`, `registry.py`, `couplings.py`, `values.py`, `readings.py`,
  `searchtexts.py`, `linereadings.py`, the `*couplings.py` parts,
  `scripts/tests/test_crosscheck.py`.
- [Reading: the census](../readings/constant-registry.md).
- [ADR-0063](ADR-0063-compose-checks.md) (the compose checks),
  [ADR-0029](ADR-0029-vision-screen-capture.md) (the first linked value),
  [ADR-0043](ADR-0043-subagent-server-flags.md) (the flag rule, whose budget lives here),
  [ADR-0044](ADR-0044-document-rosters.md) (name lists, which this registry does not cover).
