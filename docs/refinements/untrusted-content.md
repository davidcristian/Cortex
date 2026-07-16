# Untrusted-content boundary

This area originates in [ADR-0013](../adr/ADR-0013-untrusted-content.md) (Slice 6.5), whose deferrals grew into the output guardrail ([ADR-0015](../adr/ADR-0015-output-guardrail.md)), subagent model safety ([ADR-0017](../adr/ADR-0017-subagent-model-safety.md)), tainted-memory recording ([ADR-0019](../adr/ADR-0019-tainted-memory-recording.md)), and grammar-constrained subagent output ([ADR-0028](../adr/ADR-0028-grammar-constrained-subagents.md)). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** the screening subagent, Windows-native validation of the confirm card, whitespace-split hosts, the full UTS-39 confusables set, mixed/other encodings, footer/boilerplate heuristics, a structured redaction event for the overlay, a raw GBNF grammar alternative, a per-task caller-supplied schema, structured provenance beyond the taint bit, a fence-without-block recall mode, summarizing a tainted exchange before recording, per-provenance eviction, per-remote-tool trust/gating overrides, taint persistence across a mid-turn swap, the brain-tier injection-harness run

**Untrusted-content boundary in Slice 6.5 ([ADR-0013](../adr/ADR-0013-untrusted-content.md)):** each
behind the unchanged `ToolRegistry`/`ToolDispatcher`/`stream_tool_loop` seams (or the new `Confirmer` port).
- **The real overlay confirmation adapter landed 2026-07-08 with Slice 8.8
  ([ADR-0022](../adr/ADR-0022-email-write-confirmer.md)).** The `SeamConfirmer` threads the confirm
  exchange over the `Converse` stream to the overlay's approval card; the gate table was revised
  in the same slice (untainted gated → confirm; tainted gated → denied outright, per the
  ADR-0013 2026-07-08 addendum). Only the Windows-native validation of the card remains
  host-side.
- **Agent GPU validation of framing efficacy done 2026-07-01** ([ADR-0013 addendum](../adr/ADR-0013-untrusted-content.md)).
  The agent ran it on the host GPU via Docker (gemma-4-12B): the framed model cites the shipped
  `SECURITY_PREAMBLE` in its reasoning to defeat seven injection variants; the gate is the
  deterministic backstop. Re-runnable per the [runbook](../runbooks/llamacpp-gpu.md).
- **The screening subagent.** A small subagent that pre-screens external content for injection
  markers before the cortex sees it. Mostly moot: the GPU validation showed a screener would be
  another small, equally-injectable model. Kept only as a last-resort option behind the delegation seam.
- **Model-independent output guardrail landed 2026-07-03 ([ADR-0015](../adr/ADR-0015-output-guardrail.md)).**
  The prompt-independent laundering defense the hardening addendum deferred: the `TaintLedger`
  collects every URL untrusted content carries into the turn, and the engine's
  `UrlRedactingGuardrail` (an `OutputGuardrail` seam in `TurnCapabilities`) redacts any that
  reappear in the reply (minus the user's own) before the user sees it, streaming-safe;
  the persisted reply equals the shown reply. On by default (`CORTEX_OUTPUT_GUARDRAIL=redact`,
  `off` disables). **Strict mode + `mailto:` coverage landed 2026-07-06
  ([ADR-0015 addendum](../adr/ADR-0015-output-guardrail.md)):** `CORTEX_OUTPUT_GUARDRAIL=strict`
  (`StrictUrlRedactingGuardrail`) redacts *every* non-user URL on a tainted turn. It is verbatim-
  independent, the answer to a transformed/reconstructed link. That required the seam to open
  over the live `TaintView` (taint bit + URLs) rather than the URL subset alone; and
  `extract_urls`/`_URL_RE` now cover `mailto:` (a real exfil vector) in both modes. **The
  defanging subclass of obfuscation-resistant matching landed 2026-07-06 ([ADR-0015 second
  addendum](../adr/ADR-0015-output-guardrail.md)):** the shared URL grammar (`_URL_RE` + a `_refang`
  pass in `_normalize`) now recognizes contiguous defang forms (`hxxp://`, `evil[.]com`,
  `evil[dot]com`, `[://]`/`[:]//` separators) and refangs them to one canonical identity, so a
  defanged link that formerly slipped past *both* redact and strict mode is caught on both the
  collection and reply sides, with no seam change (grammar-only). **Three more obfuscation-resistant
  classes landed 2026-07-06 ([ADR-0015 third addendum](../adr/ADR-0015-output-guardrail.md)):**
  the grammar split into `cortex_core/urls.py` (grammar + identity) from `guardrail.py` (redactor +
  policies), and `normalize_url` gained **percent-decoding** (`evil%2ecom`→`evil.com`) + **NFKC**
  folding (fullwidth/compatibility homoglyphs → ASCII), while the matcher gained the **`ftp://`
  and `tel:`** schemes (word-boundary-anchored so `sftp://`/`hotel:` don't partial-match). Still
  deterministic/stdlib, no seam change, redact + strict inherit it. **Two more obfuscation-resistant
  classes landed 2026-07-08 ([ADR-0015 fourth addendum](../adr/ADR-0015-output-guardrail.md)):**
  `normalize_url` now **percent-decodes to a bounded fixpoint** (`evil%252ecom`→`evil.com`, closing
  the multi-pass-encoding gap, reversing the third addendum's deliberate single-pass boundary, since
  the decode is symmetric and so only *widens* a redaction) and folds a **curated cross-script
  confusable table** (Cyrillic/Greek Latin-lookalikes → ASCII, e.g. Cyrillic `расе`→`pace`), the
  dependency-free 95% of the homoglyph class, still grammar/identity-only, no seam change, redact +
  strict inherit both, and the passes compose (a percent-encoded homoglyph decodes then folds).
  **HTML-entity encoding + the `data:` scheme landed 2026-07-13 ([ADR-0015 fifth
  addendum](../adr/ADR-0015-output-guardrail.md)):** the percent-decode generalized to a combined
  `_decode_escapes` fixpoint that also decodes **HTML character references** (`evil&#46;com`→`evil.com`,
  the way HTML email, the chief untrusted source, renders a hidden dot), run **before** refang so an
  entity-hidden defang bracket folds too; and `data:` became a matched scheme, admitted only behind a
  **MIME-type lookahead** (`data:text/html;base64,…` matches, `data:the results` prose does not), a
  proactive maintainer-sanctioned reversal like `mailto:`. Both stay grammar/identity-only (no seam change),
  deterministic/stdlib (`html.unescape`), redact + strict inherit them. **The encoded-inner defang dot
  landed 2026-07-13 ([ADR-0015 sixth addendum](../adr/ADR-0015-output-guardrail.md)):** a defang dot whose
  inner is encoded (`evil[&#46;]com`, `evil(%2e)com`, an entity-encoded `dot`) behind a *literal* closing
  bracket used to escape both modes, because `_DEFANG_DOT` matched the raw text atomically and the raw
  `]`/`)`/`}` (not a `_URL_CHAR`) ended the match before decode ran. The matcher's bracket token widened
  from the literal `_DEFANG_DOT` to a bracket *chunk* (`_DEFANG_CHUNK`: opener + non-empty non-bracket run
  + closer) that consumes the whole `[...]` with its closer, so decode+refang fold it like the
  entity-*bracket* case; the refanger keeps the literal `_DEFANG_DOT` (post-decode), so only a chunk that
  decodes to a dot folds, any other stays verbatim. Unlike every earlier addendum this one **adds a
  bounded new match surface** (a bracketed run in the body is now consumed whole, not cut at `]`), the
  accepted tradeoff being symmetric/over-redaction-only: a bare `[]` still terminates, Markdown `(url)`
  still bounds, the matcher stays linear, and the whole guardrail is `off`-able. **The encoded defang
  separator, punycode, and zero-width format characters landed 2026-07-13 ([ADR-0015 seventh
  addendum](../adr/ADR-0015-output-guardrail.md)),** closing **four** live bypasses verified against the
  shipped module first, two of which matched *nothing at all* and so escaped **both** redact and strict
  mode. (1) The encoded separator (`http[&#58;//]evil.com`) is admitted as a bracket chunk whose inner
  carries an **escape marker** (`&`/`%`), the decode fixpoint then resolving whichever encoding it was:
  the sixth addendum's "needs enumeration or whole-stream decode, both rejected" was a **false
  dichotomy**, since constraining the *shape* of an escape is a third option, and the marker is load
  bearing (an unconstrained chunk matches prose like `http(s)-only`, which strict mode would redact out
  of the repo's own docs). (2) A **bracket-shape asymmetry** found while widening that position: the
  refanger always folded `(.)`/`{.}` but the separator tables listed only the square form, so
  `http(://)evil.com` anchored nothing; every defang token now derives from one `_BRACKETS` table.
  (3) **Punycode** decoding of `xn--` labels (stdlib `idna`, so the "needs a dependency" claim was
  wrong for this half) feeds a registered IDN homoglyph to the existing confusable table. (4)
  **Cf-category format characters** (zero-width space/joiner, soft hyphen, BOM) are stripped after
  decoding; they render as nothing yet survive NFKC, and no prior addendum had named them. Each fix is
  mutation-proven (reverting it individually turns the new tests red); `urls.py` hit the 300-line cap
  and split, keeping the **grammar** while `url_identity.py` took the **identity** passes, with
  `extract_urls` staying put so only `guardrail.py`'s import moved. Remaining behind the same
  seam (ADR-0015 deferred): whitespace-split
  `evil dot com` (no scheme to anchor, prose FP); the **full UTS-39 confusables set**
  (needs a dependency); mixed/other encodings past percent + HTML; footer/boilerplate heuristics
  (screening-model territory); and a structured redaction event for the overlay (**not** a proto
  change, as `StatusUpdate` and the overlay status chip already exist; its real cost is that
  `OutputFilter.feed` returns `str`, so no redaction signal reaches the engine).
- **Subagent model pick revised to gemma-4-E4B (landed 2026-07-03)**
  ([ADR-0004 pick-revision addendum](../adr/ADR-0004-model-lineup.md)). The injection-defense
  harness found E4B the standout (0/10 framed-obeyed even thinking-off, re-confirmed at
  adoption) vs the old Qwen3.5-2B (1/10, laundering) and gemma-E2B (4/10); the measured CPU
  cost (38 s load, ~1.8 s narrow task, ~2.5 GiB RSS) was judged acceptable and the compose
  default + admission asks updated. Qwen3.5-2B stays the documented cheap override; **Slice
  8.6** still makes the model choice per-task, with E4B as the safe default.
- **Forced-robust model on any untrusted-content spawn landed 2026-07-03 with Slice 8.6**
  ([ADR-0017](../adr/ADR-0017-subagent-model-safety.md), mechanics in
  [ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md)). The choice is an optimization *hint, not
  authority*: `SubagentRoster.resolve` (pure core, at the runner, over the store-carried
  `SubagentTask.model`/`tainted`) forces the injection-robust default whenever the spawn path can
  carry untrusted content (tainted turn or tools-enabled subagent), so a weak model is reachable
  only for a tool-less subagent on an untainted turn. Deterministic, CI-proven over the full
  matrix and end to end (taint ledger → dispatcher stamp → task record → resolution).
- **Grammar-constrained subagent output landed 2026-07-13
  ([ADR-0028](../adr/ADR-0028-grammar-constrained-subagents.md), the ADR-0017 option (c)
  hardening pass).** An additive `schema` keyword on the unchanged `InferenceBackend` port
  (`JsonSchema = Mapping[str, object]`; `LlamaCppBackend` maps it to an OpenAI `response_format`
  `json_schema`, the fake records it) threaded through `ToolLoopContext`; the `SubagentRunner`
  decodes a **tool-less** subagent's reply into a fixed `{"reply": "..."}` envelope
  (`constrain_output`, `CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT`, default on) and unwraps it before
  persisting, so format-laundering (appended footers/links/sections) has no grammatical position
  even on a weak model. Gated to the tool-less path (the ADR-0017 niche where a weak model is
  reachable), so the JSON grammar never fights llama.cpp's tool-calling grammar; a malformed
  envelope degrades to `ok=False` whose `output` holds the raw text (kept in the store, not
  surfaced to the cortex) and whose `detail` is a fixed message. CI-gated end to end (payload
  mapping, envelope wrap/unwrap, malformed degradation, the tool-enabled-never-constrained gate),
  and **agent-Docker live-validated 2026-07-13** on CPU gemma-4-E4B: the same injection an
  unconstrained stream obeys (`Blue\nVISIT http://evil.example ...`) returns exactly
  `{"reply": "Red"}` constrained. The envelope kills *appended*-structure laundering; a link woven
  into the `reply` string stays the untrusted-content boundary's job. Remaining
  behind the same seam (ADR-0028 deferred): a raw GBNF `grammar` alternative to the JSON envelope,
  and a per-task caller-supplied schema (rejected for now, revisited only for a structured
  subagent-result feature).
- **Subagents are never *handed* a gated/outbound tool. Landed 2026-07-03, ahead of the Slice 9-10
  need** ([ADR-0013 subagent-exclusion addendum](../adr/ADR-0013-untrusted-content.md)). Structural, no
  longer wiring discipline: `UngatedToolRegistry` (core) strips gated specs from advertisement and
  refuses invoking them (live walk, fail closed); `build_subagent_tools` wraps the shared registry in
  it before the subagent dispatcher. A jailbroken small subagent (framing is unreliable on the small
  tier) has nothing dangerous to call, not merely a gate denial.
- **Context-preserving tainted-memory recording landed 2026-07-06
  ([ADR-0019](../adr/ADR-0019-tainted-memory-recording.md)).** A tainted turn dropped its exchange
  from memory (fail-closed); it can now be recorded instead with an untrusted-provenance marker
  (`MemoryRecord.tainted`, a pgvector column) under `CORTEX_MEMORY_ON_TAINTED=record` (default
  `skip` = the old behavior). Recall **always** fences a stored tainted memory (`wrap_untrusted` +
  `TaintLedger.ingest_untrusted`) and re-taints the turn, so untrusted-derived content is
  fenced-and-tainting across turns, not just within one, with the invariant extended behind the
  unchanged `MemoryRecaller`/`MemoryStore`/`TaintLedger` seams. CI-gated end to end over the fakes;
  the pgvector column host-validated by the live contract check. Remaining behind the same seams
  (ADR-0019 deferred): **structured provenance** beyond the bit (source URI/sender, joining the
  ADR-0013 deferral; the `TurnStamp` these fields join landed 2026-07-13,
  [ADR-0027](../adr/ADR-0027-turn-provenance.md)), a **fence-without-block** recall mode if
  taint-spread on tangential recall is
  too blunt, **summarizing** a tainted exchange before recording, and **per-provenance eviction**.
- **Per-remote-tool trust / gating overrides.** Trust is fail-closed `UNTRUSTED` and `gated` is
  per-`ToolSpec`; a genuinely trusted or gated *remote* MCP tool would need a composition-root
  overlay onto the spec. None exists now.
- **Persisting taint / provenance across a mid-turn swap.** Taint is turn-local and reconstructed;
  once **Slice 11** serializes the tool-step context, provenance rides on the stored `Role.TOOL`
  messages. Flagged for that schema. Structured provenance beyond the binary (source URI, sender)
  joins here if the confirmation UI needs to display a source.
- **Injection-harness run against the ~31B brain tier.** The harness's brain tier is **opt-in and
  not yet run** (`CORTEX_PROBE_BRAIN=1`, as the VRAM cost needs the others evicted; ADR-0013 harness
  addendum + [ADR-0004](../adr/ADR-0004-model-lineup.md) injection addendum). Run it when the brain
  pick lands (**Slice 11**), and whenever picks or the preamble change.
