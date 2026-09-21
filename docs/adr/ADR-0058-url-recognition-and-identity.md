# ADR-0058: What the output guardrail recognizes as a URL, and when two forms are one link

**Status:** Accepted (2026-08-17)

## Context

The output guardrail ([ADR-0015](ADR-0015-output-guardrail.md)) acts only on text its matcher
recognizes as a URL, and its default policy removes a link only when the reply's identity for it
equals one collected from untrusted content. So two things decide what it catches: the **grammar**
(what counts as a link, even one half-streamed) and the **identity** (when two forms name one
link). A form the grammar does not admit matches nothing, and every policy is blind to it; a form
whose identity differs from its plain twin leaks under the default policy on whichever side writes
it oddly, including the collection side, where untrusted content that writes its own link oddly puts
a wrong host in the ledger and the plain reply then passes.

A deployed model can be told to rewrite a link, and on the small tier it does: the subagent tier was
measured writing `hxxps://payroll-verify dot example slash claim` under the shipped framing. Every
widening of the grammar risks the opposite failure, prose read as a link, so each form is admitted
or declined on a stated test. The measurements, including the corpus and live-model readings, are in
[docs/readings/output-guardrail.md](../readings/output-guardrail.md).

## Decision

### The rule every form is decided by

1. **A form is admitted when a resolver in this system's path turns it back into the link.** The
   path was traced end to end: the reply reaches the overlay as a React text child, with no Markdown
   renderer, no HTML sink and no linkifier, so on the reply side the resolver is the browser URL
   parser the user pastes into (the WHATWG parser, measured in `node`). On the collection side an
   HTML email is unescaped once by the sidecar (`html_to_text`) before the ledger sees it, while a
   file read through a tool arrives raw. The resolvers are therefore **one HTML rendering pass**,
   the **URL parser**, the **IDNA codec**, and the **reader undoing a defang**. A form no resolver
   undoes is declined however much it looks like a link. Source-code escapes (`\u002e`, `\x2e`,
   `\056`, `\.`) are resolved by a compiler that is not in the path, and the parser reads
   `https://evil\u002eexample` as a different host; a Markdown renderer would change that result for
   the whole CommonMark escape family, and none exists here.
2. **The layer is deterministic and uses the standard library only.** No passage classifier and no
   data file: a judgement about meaning belongs with the framing, and a table that changes with each
   Unicode release breaks the property that both sides of the defense fold the same way.
3. **A widening is measured against the repo's own prose before it is committed**, the corpus read
   from the index so the change's own examples cannot pollute it. The bar is zero spans added, and
   an extended span or a changed identity is a leak rather than a false positive (decision 17). A
   false positive can cost only a redaction under `strict` or `lookalike` on a tainted turn; the
   default policy replaces a match only when its identity was collected.

### The grammar (`urls.py`, `url_separators.py`, `url_removals.py`)

4. **Schemes.** Authority schemes `http`, `https`, `ftp` and the defanged `hxxp`, `hxxps`; opaque
   schemes `mailto:` and `tel:`; `data:` only behind a MIME lookahead (`type/subtype`, or the `,` or
   `;` that begins the data), so `data:the results` stays prose. Every scheme is anchored at a word
   boundary, so `sftp://` and `hotel:` are not misread. A bare domain or address with no scheme is
   out: matching every bare domain would redact `setup.py`-shaped prose. The scheme table produces
   both the matcher and the streaming hold-back, so they cannot disagree.
5. **Every separator is generated per character, never listed whole.** The colon is `:` or `：`
   (U+FF1A); the solidus is `/`, `／` (U+FF0F) or `\`, the URL parser's own solidus for a special
   scheme. Each glyph HTML names also gets its one-pass references (`_entity_forms`: decimal,
   hexadecimal, named; leading zeros; hexadecimal case-insensitive; names case-sensitive, since
   `&COLON;` resolves nowhere; a semicolon-less reference ends where its digits end, so `&#58123` is
   one reference). So any mixture matches: all 2,601 colon and solidus combinations fold to the one
   identity. A stacked reference (`&amp;#58;`) needs two passes and is declined; a bracketless
   percent-encoded separator or scheme (`https%3A//`) is resolved by nobody; the fullwidth reverse
   solidus U+FF3C is rejected by the parser and stays out.
6. **Defang.** The bracket vocabulary is one table (`[]`, `()`, `{}`), and every defang token comes
   from it: separators `[://]`, `[:]//`, `mailto[:]`, dots `[.]` and `[dot]` in each shape. The
   matcher consumes a whole bracket **chunk** (a non-empty inner holding no bracket) before deciding
   what it means, so an encoded inner (`evil[&#46;]com`) folds after decoding while `[0]` in a query
   stays as written; a bare `[]` still ends the match. At the separator position a chunk is admitted
   only when its inner has an escape marker (`&` or `%`), so `http(s)-only` prose is never a
   separator. Defang is recognized only inside a URL that has a scheme.
7. **A special scheme reaches its host with two solidi, one, or none**, as the parser does. The
   slashless separator is the opaque separator, at most one solidus, and a **host lookahead** that
   consumes nothing: a dotted name (the dot in any reading the identity folds, including one percent
   escape, since a parser decodes a host once), a bracketed literal with a colon (IPv6), or a split
   host (decision 8). A single label is declined, and that decline is the whole budget:
   `https:scheme` and `http:foo` are how prose names a scheme, and a bare label is registrable under
   no public suffix.
8. **A whitespace-split host.** A gap is blanks around a dot token (the word `dot`, any reading of
   the dot, or the bracketed form), admitted only right after the separator and only while no label
   so far has a plain dot: defanging replaces a host's dot and never adds one, so a host with a
   plain dot is finished and the words after it are prose. It is a branch tried ahead of the
   ordinary body, scoped to authority schemes. A blank is a space, a tab, or one of the fifteen
   codepoints NFKC folds to a space (a test regenerates that set from `unicodedata`); a line break
   is where a wrapped sentence breaks and is never a gap. `evil dot com` with no scheme stays out
   with its plain twin.
9. **A tab is a removal, not a form.** The URL parser deletes ASCII tabs and newlines before it
   parses. The tab is admitted in the body and between any two characters of any literal the grammar
   defines (`permeable`), but not in the host classes (so a tabbed gap still reads as a gap) and not
   inside a reference's digits or name (one rendering pass resolves no `&#5<TAB>8;`). The line break
   stays out: admitting it extended 42 existing spans in the corpus, each a link at a line end
   swallowing the next line's first word.

### The identity (`url_identity.py`, `url_confusables.py`)

10. **`normalize_url` runs nine passes in a fixed order**, each only ever merging two forms: (1)
    decode HTML references and percent-escapes until nothing changes, bounded by
    `_MAX_DECODE_PASSES`; (2) undo a defang; (3) strip format characters (Unicode `Cf`, zero-width
    and directional marks); (4) decode punycode labels through the standard library's `idna` codec,
    per label; (5) NFKC; (6) the curated confusable fold; (7) fold the IDNA label separators NFKC
    leaves (U+3002, U+FF61) and close a gap; (8) drop the tab; (9) fold a special scheme's
    backslashes to solidi and its authority slash run (none included) to one pair. Then trailing
    prose punctuation is dropped and scheme and authority lowercased; path, query and fragment keep
    their case. Decoding first is what exposes an entity-hidden defang, an encoded zero-width
    character or an encoded homoglyph to the passes after it. The tab is dropped after the gap fold,
    so `evil<TAB>dot<TAB>com` keeps the reader's reading (`evil.com`) rather than the parser's
    (`evildotcom`), which names a host an attacker would have to register separately. An opaque URL
    folds whole.
11. **Every pass is symmetric and every admitted form is one the identity folds**, so a widened
    matcher never produces matches that compare equal to nothing, and folding on both sides only
    ever widens a redaction.
12. **The confusable fold is a small curated table and the one judgement.** Pass 6 folds the
    Cyrillic and Greek letters that render as an ASCII Latin letter (29 entries, all in UTS-39). It
    is the only pass that is not a resolver's reading, since a confusable host is a different host,
    so it lives in its own module and callers may switch it off (`confusables=False`), which is how
    the lookalike ground reads a host (ADR-0015 decision 8). The table grows one character at a
    time, only on a measured model reproducing that character.

### Streaming and module shape

13. **The hold-back (`url_holdback.py`) keeps whatever may still grow into a match**: a match
    touching the buffer end, any prefix of a scheme opening, an unfinished reference (`https&#5`,
    with the `&` required so `database` is not held), a slashless opening whose host is arriving
    (the colon required), and a dotless label whose gap is opening. The grammar defines its host
    anchor twice, finished and arriving, from one parameterized function. Its tail comparison drops
    removals first. Prose that might still grow a host is kept until the flush and released whole;
    keeping is not redacting.
14. **The grammar lives in six modules split by responsibility**: `urls.py` (what a URL is, and
    `extract_urls`, the single entry point both sides share), `url_separators.py` (what one
    character may be written as), `url_removals.py` (what the parser deletes), `url_holdback.py`
    (what may still be growing), `url_identity.py` (the passes) and `url_confusables.py` (the
    judgement). `SPECIAL_SCHEMES` lives with the fold that reads it, and `LABEL_SEPARATORS` is
    imported by the forms module, so grammar and identity cannot disagree about what a dot is.
15. **Every widening is verified at every two-way split point** of its probes under every policy and
    at one character at a time, each agreeing with the whole-string feed.

### Declined

16. **The full UTS-39 confusables set.** Of its 6,565 single-codepoint mappings, those aimed at an
    ASCII host character need a 483-entry table beyond NFKC; the bundled UCD cannot name 41 of them;
    the mixed-script mappings are loose (`ш` to `w`, `б` to `6`); and against a chosen homoglyph a
    bigger table is still not a boundary, where the lookalike ground is.
17. **A host that mixes a plain dot and a gap** (`http://www.evil dot com`, which puts `www.evil` in
    the ledger). Relaxing the dotless rule extends existing correct matches over the prose after
    them (22 spans in the corpus), so `http://example.com dot the file` becomes
    `http://example.com.the` and the guardrail **delivers a link it catches today**. It reopens only
    with a two-reading defense, which must answer four call sites together: `extract_urls`, `_scrub`
    (non-overlapping `URL_RE.sub`), `_redacted` (trailing punctuation) and `held_from` (a later
    second reading released before it is recognized).
18. **The word `slash` for a solidus, and the `at` of a defanged address.** Once the host is gone
    the rest names nowhere, and an address is not a host.

## Consequences

- A rewritten link is caught by every policy whenever some resolver in the path would undo the
  rewriting, and the default policy catches it on either side.
- Code snippets that write a slashless or backslashed URL with a real host (`/^https:\/\/x\.com/`)
  are matches, redacted under `strict` or `lookalike` on a tainted turn and untouched by default
  unless their identity was collected; a tab right after a link joins the match, so those policies
  also remove the word after it. The fullwidth solidus as a single slash is admitted though a parser
  rejects it, to keep one solidus table.
- Some prose (`the https:scheme`) arrives one delta later, being kept while it might grow a host.

## Alternatives rejected

- **Decoding the whole stream before matching**, which abandons span-preserving redaction, and
  **enumerating encodings in the anchor**, which the repeated decoding exists to avoid; a shape
  constraint (the escape marker) is admitted where an enumeration is not.
- **A known-TLD tail, a stopword list or an adjacency rule** for the split host: the dotless rule
  needs no table, and `dot com` is ordinary English.
- **Holding back on any trailing space**, which held every URL in every reply.

## Related

- [ADR-0015](ADR-0015-output-guardrail.md) (the policies),
  [ADR-0013](ADR-0013-untrusted-content.md).
- Readings: [output-guardrail](../readings/output-guardrail.md).
- Module: [brain-core](../modules/brain-core.md).
