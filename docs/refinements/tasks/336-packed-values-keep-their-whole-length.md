# Packed values keep their whole length

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a deployment that really sets `CORTEX_LOG_FORMAT=packed`, or a collector in front of
it that reads entries rather than lines. Both limbs come off the compose files:
`grep -rn "LOG_FORMAT" docker/` reports the rendering each service ships with, and the services
those files declare are where a collector would be. This entry's trail records what that reading
answered when it was last taken, and what a packed line of the widest shipped record measures.
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-19

The per-value bound landed in `render_value`, which only the plain rendering spends.
`PackedFormatter` hands `record_fields(record)` straight to `json.dumps`, so a field of any size
reaches a packed line whole. What the two renderings share is more than this entry first said. Both
withhold a secret-named field's value in `record_fields`, and a value under a secret-named key at
any depth inside a structured field, and both end in `redact_urls` over the
whole rendered line, which the packed suite asserts on a record carrying a credential in its
message, in a field and in a traceback
(`test_the_packed_rendering_carries_a_traceback_and_withholds_the_same_secrets`). What the packed
rendering does not have is the bound, and the per-value credential pass `render_value` runs before
the bound cuts.

The asymmetry was argued rather than overlooked (ADR-0038 bounded-value addendum): the whole value
of a rendering meant to be collected is that the object parses, and a bound inside it either
corrupts the object or lies about its shape, which is the argument for cutting the plain rendering
running the other way. What is not settled is that the exposure goes away with it. A collector
meets the same 16 KiB message split the plain reader does, one JSON object arriving as several
entries, and the one that reassembles them is `docker compose logs` rather than anything
downstream of it.

Three shapes are available and none is obviously right. The line could carry the bound as a sibling
key, say `fields_cut`, naming the fields that were shortened, which keeps the object parseable at
the cost of a key nothing else uses. The packed rendering could pass values through `render_value`
and become a line of rendered strings, which is a different rendering rather than a bounded one. Or
the bound could stay a plain-rendering rule and the packed one could be documented as unbounded on
purpose, which is where it stands today and is only accurate while nobody runs it.

A fourth shape has an implementation in the tree since 2026-09-17, written for the tool audit file
rather than for this rendering. `durable_value` in
`brain/packages/tools/src/cortex_tools/audit_file.py` keeps a field as its parsed JSON value when
the plain line prints it whole, and as the plain line's own rendering, cut marker included, when
the bound cut it or a credential was withheld across a string boundary. The object still parses and only a cut field changes type, to a string. Reusing it
here would mean moving it into `cortex_core`, since `PackedFormatter` lives there and `cortex_core`
imports no adapter package.

## Trail

- 2026-09-19: trigger swept a sixth time and not fired. `docker/docker-compose.yml` still ships
  `CORTEX_LOG_FORMAT` as `plain` and `docker/docker-compose.gpu.yml` ships
  `CORTEX_MODELHOST_LOG_FORMAT` the same way, no `.env` is tracked, and the same eleven services
  include no collector. Two things changed since the last sweep, neither of them the trigger. The
  secret-name rule now withholds a value under a secret-named key nested inside a structured field,
  which `record_fields` does for both renderings, so the account above gained that clause. And the
  tool audit file landed with its own answer to how a JSON rendering keeps the bound, added above as
  a fourth shape. The widths were not re-measured: nothing between `record_fields` and either
  formatter changed except the nested withholding, which makes a line shorter rather than wider.
- 2026-09-15: trigger swept a fifth time and not fired, and the field that reaches a packed line
  whole is not only a model's. The compose files still ship `plain` in both variables, no `.env` in
  the tree sets either, and the eleven services they declare still include no collector. What is
  new is a caller the entry never counted: `session_id` arrives as a proto string on `ClientEvent`,
  is length-checked nowhere between the wire and `render_value`, and rides both shipped sinks'
  lines. The plain rendering cuts it like any other value; the packed one has no cut, so the body
  rather than the model is enough to make a packed line arbitrarily wide. Measured today, an
  audit-shaped record with a million characters in each of the **five** fields no call site chose
  renders at **10,603 characters plain with five cut markers and 5,000,406 packed with none**, 306
  of the driver's messages against one. The same run puts one trail record at its shipped caps at
  2,255 plain and 2,475 packed, so the packed rendering again costs **220 characters more** on a
  record carrying no over-long value, the fourth run to record that delta. The three shapes this
  entry offers are unchanged, and the argument for the third, documenting the packed rendering as
  unbounded on purpose, is one caller weaker than it was: it is accurate while nobody runs it, and
  what runs it no longer has to be a model.
- 2026-09-14: trigger swept a fourth time and not fired, and the widths re-measured. The compose
  files still ship `plain` in both variables, `CORTEX_LOG_FORMAT` in `docker/docker-compose.yml`
  and `CORTEX_MODELHOST_LOG_FORMAT` in `docker/docker-compose.gpu.yml`, no `.env` in the tree sets
  either, and the eleven services those files declare still include no collector: `brain`, `redis`,
  `postgres`, `pg-backup`, `llama-embed`, `mcp-filesystem`, `mcp-email`, `model-host`, two
  `llama-subagent` servers and the IMAP probe. `render_value` is still reached only through
  `render_fields` from `PlainFormatter.formatMessage`; the only other mentions of the three names in
  the brain are the `_surface/logs.py` re-exports. Re-measured today, the audit-shaped record whose
  four model-written fields each carry a million characters renders at **8,573 characters plain with
  four cut markers and 4,000,442 packed with none**, again 245 of the driver's messages against one.
  The same run puts one trail record at its shipped caps at 2,256 plain and 2,476 packed, so the
  packed rendering again costs **220 characters more** on a record carrying no over-long value,
  which is the same delta as 2026-09-12 against plain widths that moved. Three runs of the wide
  shape have now recorded 8,580, 8,437 and 8,573, a spread of 1.7% that comes from the level, logger
  and message each run chose, so what this entry publishes as portable is the marker count, the
  message count and that 220.
- 2026-09-12: trigger swept a third time and not fired, and this entry is not the same defect as
  [R-337](337-a-bounded-value-leaves-the-line-unbounded.md), which was the question the sweep was
  asked. The compose files are unchanged, `plain` in both variables and no collector among the
  eleven services, and `render_value` is still reached only through `render_fields` from
  `PlainFormatter.formatMessage`: a grep for all three names over the brain finds no other caller
  outside the suites. Re-measured today, the same audit-shaped record whose four model-written
  fields each carry a million characters renders at **8,437 characters plain with four cut markers
  and 4,000,296 packed with none**, 245 of the driver's messages against one. Those are not the
  8,580 and 4,000,439 of 2026-09-08, and the difference is the record's own names rather than the
  formatter: a line spends its level, logger and message before the first field, and a cut field
  spends its marker's own digits, so a width of this kind reproduces only within one run's shape and
  the portable readings are the marker count and the message count. The two entries are separate
  because neither fix closes the other: a whole-line bound in `render_fields` leaves a packed line
  unbounded, since that rendering never calls it, and passing packed values through `render_value`
  would bound each value and leave the packed line's own total unbounded exactly as R-337 says the
  plain one is. The measurement [R-470](470-the-reader-assumes-the-plain-rendering.md)'s close
  needed is this entry's subject at the other end of the scale: one trail record at its shipped caps
  renders at 2,258 characters plain and 2,478 packed, so on a record carrying no over-long value the
  packed rendering costs 220 characters more rather than 474 times as much.
- 2026-09-08: trigger swept and not fired, and one sentence of this entry corrected.
  `docker/docker-compose.yml` ships `CORTEX_LOG_FORMAT: ${CORTEX_LOG_FORMAT:-plain}` and
  `docker/docker-compose.gpu.yml` ships `CORTEX_MODELHOST_LOG_FORMAT` the same way, no `.env` in the
  tree sets either, and no compose file declares a collector: the services are `brain`, `redis`,
  `postgres`, `pg-backup`, `llama-embed`, `mcp-filesystem`, `mcp-email`, `model-host`, two
  `llama-subagent` servers and the IMAP probe. The size the trigger is about was measured today
  rather than argued. One `LoggingAuditSink`-shaped record whose model-written `tool`, `call_id`,
  `arguments` and `error` each carry a million characters renders through `PlainFormatter` at
  **8,580 characters with four cut markers**, and through `PackedFormatter` at **4,000,439**, which
  is 245 of the driver's 16 KiB messages against one. The corrected sentence is the claim that the
  two renderings share the secrets rule and nothing else: both also run `redact_urls` over the whole
  line they return. The packed rendering reaches one credential the plain one misses, because its
  whole-line pass runs over JSON-escaped text and a control character inside a userinfo is two
  printing characters by then, which is the reading in
  [R-343](343-a-userinfo-the-pattern-cannot-reach.md).
- 2026-08-20: The second shape below gained an argument nobody was looking for. `render_value` now
  withholds a URL credential before the bound cuts, because a cut between a `://` and its `@`
  defeated the whole-line pass entirely (ADR-0038 cut-defeats-withholding addendum). The packed
  rendering never had that exposure, having no cut, so nothing here is more urgent; but a packed
  line routed through `render_value` would inherit the ordering rather than need it written twice.
- 2026-08-20: Opened by the close of
  [R-324](324-a-rendered-field-has-no-bound.md), which bounded the rendering an operator reads and
  deliberately left the one a collector reads alone.
