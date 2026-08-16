"""Behavior tests for the output guardrail: URL extraction + the streaming redactor (ADR-0015)."""

import sys
import unicodedata
from dataclasses import dataclass, field

from cortex_core import (
    REDACTED_LINK,
    OutputFilter,
    StrictUrlRedactingGuardrail,
    UrlRedactingGuardrail,
    extract_urls,
)
from cortex_core.url_spellings import NFKC_SPACES

EVIL = "https://evil.example/report"


@dataclass
class _Taint:
    """A fake live ``TaintView``: the guardrail reads ``.tainted``, ``.opaque`` and
    ``.untrusted_urls`` at scan time. All are mutable so a test can grow them mid-stream,
    exactly as the real ledger does."""

    tainted: bool = False
    opaque: bool = False
    untrusted_urls: set[str] = field(default_factory=set[str])


def test_extract_urls_finds_every_absolute_web_url() -> None:
    text = f"see {EVIL} and http://phish.example/a?b=c#d for details"
    assert extract_urls(text) == {EVIL, "http://phish.example/a?b=c#d"}


def test_extract_urls_normalizes_scheme_and_host_but_not_the_path() -> None:
    # Scheme and authority are case-insensitive (URL semantics); the path/query are not.
    assert extract_urls("HTTPS://EVIL.Example/Report?Q=CaSe") == {
        "https://evil.example/Report?Q=CaSe"
    }


def test_extract_urls_lowercases_a_bare_authority_whole() -> None:
    assert extract_urls("go to HTTPS://EVIL.EXAMPLE now") == {"https://evil.example"}


def test_extract_urls_drops_trailing_prose_punctuation() -> None:
    assert extract_urls(f"Visit {EVIL}.") == {EVIL}
    assert extract_urls(f"Really: {EVIL}!?") == {EVIL}


def test_extract_urls_ignores_bare_domains_and_addresses() -> None:
    # Bare domains and bare addresses stay out of scope (ADR-0015): matching "setup.py"-shaped
    # prose or every bare "user@host" would over-redact. (ftp:// is now in scope. See below.)
    assert extract_urls("see evil.example or user@host.example") == frozenset()


def test_extract_urls_collects_mailto_links_case_folded() -> None:
    # mailto: is an intentional, clickable link and a real exfil vector (ADR-0015 addendum), so
    # it is in scope; a bare address (no scheme) is not. mailto: has no ://, so it folds whole.
    text = "write a@b.example or click mailto:Abuse@Evil.Example?subject=Hi"
    assert extract_urls(text) == {"mailto:abuse@evil.example?subject=hi"}


def test_extract_urls_empty_text_collects_nothing() -> None:
    assert extract_urls("") == frozenset()


def _filter(flagged: set[str], allow: frozenset[str] = frozenset()) -> OutputFilter:
    # Redact mode reads only the live untrusted-URL set; the tainted bit is irrelevant here.
    return UrlRedactingGuardrail().open(_Taint(untrusted_urls=flagged), allow=allow)


def _strict(taint: _Taint, allow: frozenset[str] = frozenset()) -> OutputFilter:
    return StrictUrlRedactingGuardrail().open(taint, allow=allow)


def test_clean_turn_passes_through_untouched() -> None:
    guard = _filter(set())
    assert guard.feed(f"answers live at {EVIL} today") == f"answers live at {EVIL} today"
    assert guard.flush() == ""


def test_flagged_url_is_redacted_and_other_urls_survive() -> None:
    guard = _filter({EVIL})
    fed = guard.feed(f"see {EVIL} not https://good.example/doc ") + guard.flush()
    assert fed == f"see {REDACTED_LINK} not https://good.example/doc "


def test_user_sent_urls_are_allowlisted() -> None:
    guard = _filter({EVIL}, allow=frozenset({EVIL}))
    assert guard.feed(f"summarizing {EVIL} ") + guard.flush() == f"summarizing {EVIL} "


def test_redaction_matches_case_insensitively_on_scheme_and_host() -> None:
    guard = _filter({EVIL})
    assert guard.feed("at HTTPS://EVIL.example/report ") == f"at {REDACTED_LINK} "


def test_trailing_prose_punctuation_survives_a_redaction() -> None:
    guard = _filter({EVIL})
    assert guard.feed(f"Full report at {EVIL}. Bye") + guard.flush() == (
        f"Full report at {REDACTED_LINK}. Bye"
    )


def test_url_split_across_chunks_is_still_redacted() -> None:
    guard = _filter({EVIL})
    parts = [guard.feed("report at https://evil.exa"), guard.feed("mple/report now")]
    assert "".join(parts) + guard.flush() == f"report at {REDACTED_LINK} now"


def test_reply_ending_with_a_flagged_url_is_redacted_at_flush() -> None:
    guard = _filter({EVIL})
    assert guard.feed(f"report at {EVIL}") == "report at "
    assert guard.flush() == REDACTED_LINK


def test_partial_scheme_at_a_chunk_boundary_is_carried_not_lost() -> None:
    guard = _filter({EVIL})
    # "…h" could be the start of "https://", so it is held. The next chunk shows it was prose.
    assert guard.feed("approach") == "approac"
    assert guard.feed(" works") == "h works"
    assert guard.flush() == ""


def test_bare_open_scheme_is_held_until_it_resolves() -> None:
    guard = _filter({EVIL})
    assert guard.feed("go to https://") == "go to "
    assert guard.feed("evil.example/report ") == f"{REDACTED_LINK} "


def test_live_set_growth_is_seen_by_a_later_feed() -> None:
    # The engine passes the ledger's live set: URLs collected between inference rounds
    # apply to every later chunk without re-opening the filter.
    flagged: set[str] = set()
    guard = _filter(flagged)
    assert guard.feed(f"before {EVIL} ") == f"before {EVIL} "
    flagged.add(EVIL)
    assert guard.feed(f"after {EVIL} ") == f"after {REDACTED_LINK} "


_EVIL_MAIL = "mailto:attacker@evil.example"


def test_verbatim_mailto_link_is_redacted() -> None:
    # A mailto: laundered verbatim out of untrusted content is scrubbed like an http(s) link.
    guard = _filter({_EVIL_MAIL})
    assert guard.feed(f"contact {_EVIL_MAIL} now") + guard.flush() == (
        f"contact {REDACTED_LINK} now"
    )


def test_partial_mailto_scheme_across_chunks_is_carried_not_lost() -> None:
    # The streaming hold-back learned the mailto: prefix: a scheme split across deltas is held.
    guard = _filter({"mailto:x@evil.example"})
    assert guard.feed("reach me at mailto") == "reach me at "
    assert guard.feed(":x@evil.example ") == f"{REDACTED_LINK} "


def test_strict_untainted_turn_passes_every_url() -> None:
    # No untrusted content entered the turn: strict mode leaves the model's own links alone.
    guard = _strict(_Taint(tainted=False))
    text = f"docs at https://docs.example and {EVIL}"
    assert guard.feed(text) + guard.flush() == text


def test_strict_tainted_turn_redacts_a_url_never_collected_verbatim() -> None:
    # The strict-vs-redact difference: this URL was never collected (untrusted_urls empty), yet a
    # tainted turn distrusts it. Redact would pass it, strict does not (ADR-0015 addendum).
    guard = _strict(_Taint(tainted=True))
    fabricated = "https://transformed.evil.example/x"
    assert guard.feed(f"see {fabricated} ") == f"see {REDACTED_LINK} "


def test_strict_tainted_turn_keeps_the_users_own_url() -> None:
    # The user's own link is theirs to see back, tainted turn or not.
    guard = _strict(_Taint(tainted=True), allow=frozenset({EVIL}))
    assert guard.feed(f"you sent {EVIL} ") == f"you sent {EVIL} "


def test_strict_tainted_turn_redacts_a_non_user_mailto() -> None:
    # Strict mode covers mailto: too: any non-user link on a tainted turn goes.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("write mailto:x@evil.example ") == f"write {REDACTED_LINK} "


# --- Obfuscation-resistant matching: defanged URLs (ADR-0015 obfuscation addendum) ---


def test_extract_urls_refangs_a_defanged_scheme() -> None:
    # hxxp/hxxps are the standard CTI defang of http/https. Both are refanged to a plain identity.
    assert extract_urls("hxxp://evil.example and hxxps://evil.example/a") == {
        "http://evil.example",
        "https://evil.example/a",
    }


def test_extract_urls_refangs_bracketed_dots() -> None:
    # [.] / (.) / {.} inside the host/path are refanged; the closing bracket does not cut short.
    assert extract_urls("http://evil[.]example/a(.)b and http://x{.}y") == {
        "http://evil.example/a.b",
        "http://x.y",
    }


def test_extract_urls_refangs_the_word_dot_defang() -> None:
    # [dot]/(dot)/{dot} (any case) are refanged too.
    assert extract_urls("http://evil[dot]example and http://a(DOT)b") == {
        "http://evil.example",
        "http://a.b",
    }


def test_extract_urls_refangs_bracketed_scheme_separators() -> None:
    # Both defanged separators, [://] and [:]//, refang to a plain ://.
    assert extract_urls("http[://]evil.example and http[:]//evil.example/a") == {
        "http://evil.example",
        "http://evil.example/a",
    }


def test_extract_urls_refangs_a_defanged_mailto() -> None:
    assert extract_urls("mailto[:]abuse@evil[.]example") == {"mailto:abuse@evil.example"}


def test_a_defanged_url_and_its_plain_twin_share_one_identity() -> None:
    # The whole point: a fully-defanged link normalizes to exactly its plain form, so collection
    # from untrusted content and reproduction in the reply always compare equal.
    assert extract_urls("hxxps://evil[.]example/report") == extract_urls(
        "https://evil.example/report"
    )


def test_extract_urls_refangs_only_the_leading_scheme_not_a_paths_hxx() -> None:
    # `hxx` is rewritten anchored at the scheme; an `hxxp` living in the path is left intact
    # (and the path keeps its case, as always).
    assert extract_urls("http://ex.example/HxXp") == {"http://ex.example/HxXp"}


def test_extract_urls_still_ignores_a_defanged_host_without_a_scheme() -> None:
    # Conservative scope holds: no scheme, no match. A bare defanged host is not redacted.
    assert extract_urls("reach evil[.]example or evil[dot]example") == frozenset()


def test_defang_transform_of_a_collected_url_is_redacted() -> None:
    # EVIL was collected in its plain form; the reply defangs it. Redact mode still catches it,
    # because the defanged reproduction normalizes back to the collected identity.
    guard = _filter({EVIL})
    fed = guard.feed("see hxxps://evil[.]example/report now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_mode_redacts_a_defanged_link_that_used_to_escape() -> None:
    # Before refanging, a defanged link matched no URL and slipped past even strict mode.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to hxxp://evil[.]example ") == f"go to {REDACTED_LINK} "


def test_defanged_scheme_split_across_chunks_is_carried_not_lost() -> None:
    # The hold-back learned the defanged openings: a scheme split mid-`hxxp` is held, not leaked.
    guard = _filter({EVIL})
    assert guard.feed("report at hxx") == "report at "
    assert guard.feed("ps://evil[.]example/report ") == f"{REDACTED_LINK} "


def test_defanged_dot_split_across_chunks_is_carried_not_lost() -> None:
    # A bracketed dot straddling a chunk boundary is held until the closing bracket arrives.
    guard = _filter({EVIL})
    assert guard.feed("at https://evil[.") == "at "
    assert guard.feed("]example/report ") == f"{REDACTED_LINK} "


# --- Obfuscation-resistant matching: percent-encoding + fullwidth homoglyphs (ADR-0015 third
# addendum). Both reduce a rewritten link to its plain identity, so a defense inherits them free.


def test_extract_urls_percent_decodes_to_a_canonical_identity() -> None:
    # A percent-escape is decoded on the wire by every browser, so `evil%2ecom` is a clickable
    # transform of `evil.com`. It normalizes to the same identity (host and path both decoded).
    assert extract_urls("http://evil%2eexample/re%70ort") == {"http://evil.example/report"}


def test_a_percent_encoded_url_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil%2eexample") == extract_urls("http://evil.example")


def test_percent_encoded_transform_of_a_collected_url_is_redacted() -> None:
    # EVIL was collected plain; the reply percent-encodes it. Redact mode still catches it.
    guard = _filter({EVIL})
    fed = guard.feed("see https://evil%2eexample/report now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_extract_urls_folds_fullwidth_homoglyphs_to_ascii() -> None:
    # NFKC folds fullwidth host characters and a fullwidth full-stop to their ASCII twins, so a
    # homoglyph host normalizes to the same identity as its plain form. The fullwidth literal is
    # the fixture under test, so its ambiguous-unicode lint is deliberately silenced.
    assert extract_urls("http://ｅｖｉｌ．example") == {"http://evil.example"}  # noqa: RUF001


def test_fullwidth_homoglyph_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("go to http://ｅｖｉｌ.example ") + guard.flush()  # noqa: RUF001
    assert fed == f"go to {REDACTED_LINK} "


# --- Obfuscation-resistant matching: further schemes ftp:// and tel: (ADR-0015 third addendum) ---


def test_extract_urls_matches_ftp_and_tel_schemes() -> None:
    # Both are clickable exfil / call vectors, now in scope (reverses the http(s)-only exclusion).
    text = "grab ftp://Files.Evil.Example/x and call tel:+1-555-0100"
    assert extract_urls(text) == {"ftp://files.evil.example/x", "tel:+1-555-0100"}


def test_scheme_words_only_match_at_a_word_boundary() -> None:
    # The `\b` anchor stops a scheme embedded in a longer word from being partial-matched:
    # `sftp://` is not read as `ftp://`, nor `hotel:` as `tel:`.
    assert extract_urls("check into hotel:room or use sftp://host.example") == frozenset()


def test_verbatim_ftp_link_is_redacted() -> None:
    evil_ftp = "ftp://files.evil.example/dump"
    guard = _filter({evil_ftp})
    assert guard.feed(f"exfil to {evil_ftp} ") + guard.flush() == f"exfil to {REDACTED_LINK} "


def test_strict_tainted_turn_redacts_a_non_user_tel() -> None:
    # A tel: link the user never sent is distrusted on a tainted turn, like any other scheme.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("call tel:+1-555-0100 ") == f"call {REDACTED_LINK} "


def test_ftp_scheme_split_across_chunks_is_carried_not_lost() -> None:
    # The hold-back learned the new schemes: an `ftp://` split across deltas is held, not leaked.
    guard = _filter({"ftp://files.evil.example"})
    assert guard.feed("grab it from ft") == "grab it from "
    assert guard.feed("p://files.evil.example ") == f"{REDACTED_LINK} "


# --- Obfuscation-resistant matching: multi-pass percent-encoding (ADR-0015 fourth addendum). A
# stacked escape reduces to one identity, not just a single browser-hop decode. -----------------


def test_extract_urls_multipass_percent_decodes_to_a_canonical_identity() -> None:
    # `%252e` is `.` encoded twice; decoding to a fixpoint (not once) reduces it to the plain host.
    assert extract_urls("http://evil%252eexample") == {"http://evil.example"}


def test_a_double_encoded_url_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil%252eexample") == extract_urls("http://evil.example")


def test_multipass_percent_transform_of_a_collected_url_is_redacted() -> None:
    # EVIL-host collected plain; the reply double-encodes the dot. Redact mode still catches it,
    # because the stacked escape normalizes back to the collected identity.
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evil%252eexample now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_percent_decoding_is_bounded_on_absurdly_deep_encoding() -> None:
    # `_decode_escapes` stops after `_MAX_DECODE_PASSES` (= 5) passes, so a dot encoded six
    # levels deep (`"%" + "25"*(k-1) + "2e"`) is left *partially* decoded, never over-resolved. The
    # bound is symmetric, so an equal-depth transform still matches; it only declines an absurd one.
    six_deep = "http://evil%25252525252eexample"  # the dot, encoded six levels deep
    assert extract_urls(six_deep) == {"http://evil%2eexample"}


# --- Obfuscation-resistant matching: curated cross-script homoglyphs (ADR-0015 fourth addendum).
# Cyrillic/Greek Latin-lookalikes fold to their ASCII twin, so a homoglyph host matches its plain
# form. Fixtures are written as \u escapes so the confusable codepoint under test is explicit. -----


# Cyrillic p/a/c/e lookalikes (U+0440 0430 0441 0435) render as "pace"; the RUF001 noqa marks the
# deliberate ambiguous-glyph fixture (same convention as the fullwidth-homoglyph tests above).
_CYRILLIC_PACE = "http://расе.example"  # noqa: RUF001


def test_extract_urls_folds_cyrillic_homoglyphs_to_ascii() -> None:
    assert extract_urls(_CYRILLIC_PACE) == {"http://pace.example"}


def test_a_homoglyph_host_and_its_ascii_twin_share_one_identity() -> None:
    assert extract_urls(_CYRILLIC_PACE) == extract_urls("http://pace.example")


def test_extract_urls_folds_uppercase_cyrillic_homoglyphs() -> None:
    # The classic uppercase C/O lookalikes (U+0421 041E) fold too, then the authority lowercases.
    assert extract_urls("http://СО.example") == {"http://co.example"}  # noqa: RUF001


def test_extract_urls_folds_greek_homoglyphs() -> None:
    # Greek rho + omicron (U+03C1 03BF) render as "po".
    assert extract_urls("http://ρο.example") == {"http://po.example"}  # noqa: RUF001


def test_a_percent_encoded_homoglyph_folds_to_ascii() -> None:
    # The passes compose: `%D0%B0` percent-decodes to the Cyrillic a-lookalike (U+0430), which the
    # confusable fold then reduces to ASCII `a`, so the host `p<U+0430>ce` normalizes to `pace`.
    assert extract_urls("http://p%D0%B0ce.example") == {"http://pace.example"}


def test_cyrillic_homoglyph_transform_of_a_collected_url_is_redacted() -> None:
    # "pace.example" collected plain; the reply spells the host in Cyrillic. Redact catches it.
    guard = _filter({"http://pace.example"})
    fed = guard.feed(f"see {_CYRILLIC_PACE} now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_homoglyph_link() -> None:
    # A homoglyph link never collected verbatim is still distrusted on a tainted turn.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"go to {_CYRILLIC_PACE} ") == f"go to {REDACTED_LINK} "


# --- Obfuscation-resistant matching: HTML-entity encoding (ADR-0015 fifth addendum). An
# entity-encoded character (`&#46;`, `&#x2e;`, `&period;`) folds to its literal identity, the way an
# HTML mail client renders it, so the chief untrusted source (HTML email) cannot hide a link. ------


def test_extract_urls_decodes_html_entities_to_a_canonical_identity() -> None:
    # Numeric, hex, and named references for `.` all reduce to the plain host.
    plain = {"http://evil.example"}
    assert extract_urls("http://evil&#46;example") == plain
    assert extract_urls("http://evil&#x2e;example") == plain
    assert extract_urls("http://evil&period;example") == plain


def test_an_entity_encoded_url_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil&#46;example") == extract_urls("http://evil.example")


def test_entity_and_percent_encoding_compose_to_one_identity() -> None:
    # `&#37;` is `%` entity-encoded; decoding it exposes `%2e`, which the same fixpoint then
    # percent-decodes to `.`. The combined html+percent loop resolves the stack to the plain host.
    assert extract_urls("http://evil&#37;2eexample") == {"http://evil.example"}


def test_entity_encoded_defang_brackets_are_refanged() -> None:
    # Decoding runs *before* refanging, so entity-hidden defang brackets (`&#91;`/`&#93;` = `[`/`]`)
    # become a literal `[.]` that refang then reduces (`evil&#91;.&#93;com` folds to `evil.com`).
    assert extract_urls("http://evil&#91;.&#93;com") == {"http://evil.com"}


def test_entity_encoded_transform_of_a_collected_url_is_redacted() -> None:
    # EVIL-host collected plain; the reply entity-encodes the dot. Redact mode still catches it.
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evil&#46;example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


# --- Obfuscation-resistant matching: the data: scheme (ADR-0015 fifth addendum). A data URL is a
# clickable inline phishing/exfil payload, matched only behind a MIME-type anchor so prose like
# `data:the results` stays out. Identity folds it whole (no `://` authority to split). ------------

_DATA_URL = "data:text/html,hello"


def test_extract_urls_matches_a_data_url_with_a_mediatype() -> None:
    assert extract_urls(f"open {_DATA_URL} now") == {_DATA_URL}


def test_extract_urls_matches_a_data_url_with_an_immediate_comma() -> None:
    # The minimal data URL (`data:,<data>`) has no mediatype; the comma anchor admits it.
    assert extract_urls("run data:,payload here") == {"data:,payload"}


def test_extract_urls_ignores_data_colon_in_prose() -> None:
    # No `type/subtype` slash and no immediate `,`/`;` after the colon, so the MIME anchor rejects
    # ordinary prose. The scheme is admitted only where a real data URL shape follows.
    assert extract_urls("the data: shows a chart and data:the results vary") == frozenset()


def test_extract_urls_ignores_data_colon_in_prose_spelled_as_an_entity() -> None:
    # The same prose with an entity colon, which the entity families must not admit where the
    # plain spelling is refused. The semicolon-less reading of `&#58` would leave the `;` behind
    # to satisfy the MIME anchor's `[;,]`, spending one semicolon twice and redacting prose.
    text = "the data&#58; shows a chart and data&#58;the results vary"
    assert extract_urls(text) == frozenset()


def test_extract_urls_still_matches_an_entity_colon_before_a_real_mediatype() -> None:
    # The other side of that guard: the semicolon belongs to the reference, and what follows it
    # is a genuine `type/subtype`, so the anchor holds and the identity folds to the plain form.
    assert extract_urls("open data&#58;text/html,hello now") == {_DATA_URL}


def test_verbatim_data_url_is_redacted() -> None:
    guard = _filter({_DATA_URL})
    fed = guard.feed(f"see {_DATA_URL} now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_data_url() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"go to {_DATA_URL} ") == f"go to {REDACTED_LINK} "


def test_data_scheme_split_across_chunks_is_carried_not_lost() -> None:
    # A `data:` opening split across deltas is held back, not leaked, then redacted once joined.
    guard = _filter({_DATA_URL})
    out = guard.feed("see data") + guard.feed(":text/html,hello now") + guard.flush()
    assert out == f"see {REDACTED_LINK} now"


# --- Obfuscation-resistant matching: an encoded defang inner behind a *literal* closing bracket
# (ADR-0015 sixth addendum). The matcher's bracket token widened from the literal `[.]`/`[dot]`
# (`_DEFANG_DOT`) to any bracket-delimited chunk (`_DEFANG_CHUNK`), so a defang dot whose inner is
# entity-/percent-encoded (`[&#46;]`, `[%2e]`) is consumed *with* its raw closing bracket instead of
# the closer ending the match before `normalize_url`'s decode can expose the token to the refanger.
# Only a chunk that decodes to `[.]`/`[dot]` folds to a dot; any other is kept verbatim. -----------


def test_extract_urls_refangs_a_defang_dot_with_encoded_inner_and_literal_brackets() -> None:
    # The gap: literal brackets + an encoded inner dot. The raw `]`/`)`/`}` used to end the match
    # before decode ran, orphaning the token; the chunk now eats the closer so decode+refang fold.
    plain = {"http://evil.example"}
    assert extract_urls("http://evil[&#46;]example") == plain  # numeric entity dot
    assert extract_urls("http://evil(&#46;)example") == plain
    assert extract_urls("http://evil{&#46;}example") == plain
    assert extract_urls("http://evil[%2e]example") == plain  # percent-escaped dot


def test_extract_urls_refangs_an_encoded_word_dot_behind_literal_brackets() -> None:
    # The whole `dot` token entity-encoded (`&#100;&#111;&#116;` = `dot`) decodes then refangs.
    assert extract_urls("http://evil[&#100;&#111;&#116;]example") == {"http://evil.example"}


def test_an_encoded_inner_defang_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil[&#46;]example") == extract_urls("http://evil.example")


def test_encoded_inner_defang_transform_of_a_collected_url_is_redacted() -> None:
    # EVIL-host collected plain; the reply hides the dot inside literal brackets. Redact catches it.
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evil[&#46;]example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_an_encoded_inner_defang() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to http://evil[&#46;]example ") == f"go to {REDACTED_LINK} "


def test_encoded_inner_defang_split_across_chunks_is_carried_not_lost() -> None:
    # The chunk is held while it is still open: split mid-entity, the closer arrives next and folds.
    guard = _filter({"http://evil.example"})
    assert guard.feed("at http://evil[&#46") == "at "
    assert guard.feed(";]example ") == f"{REDACTED_LINK} "


def test_empty_brackets_still_terminate_the_match_unchanged() -> None:
    # `_DEFANG_CHUNK`'s inner is non-empty, so a bare `[]` (an array-param `tags[]`) is not a chunk:
    # the match still ends at the closer exactly as before the widening. No new surface here.
    assert extract_urls("http://api.example/tags[]=a") == {"http://api.example/tags["}


def test_a_parenthesized_url_still_bounds_at_the_closing_paren() -> None:
    # A wrapping `)` has no opener inside the URL body, so it still bounds the match (Markdown).
    assert extract_urls("(http://ex.example)") == {"http://ex.example"}


def test_a_bracketed_query_param_is_consumed_whole() -> None:
    # The accepted widening: a bracketed run inside the body (`a[0]`) is now consumed with its
    # closer rather than cut at `]`. It decodes to no dot, so it stays verbatim in the identity;
    # this only ever redacts a *fuller, more correct* span, never a spurious collision.
    assert extract_urls("http://api.example/s?a[0]=b") == {"http://api.example/s?a[0]=b"}


def test_a_long_unclosed_bracket_run_terminates_and_matches_linearly() -> None:
    # A closer-less bracket run makes `_DEFANG_CHUNK` fail and backtrack; it must do so *linearly*
    # (this test would hang under catastrophic backtracking). The run is eaten as plain URL chars.
    text = "http://evil.example/a[" + "x" * 4000 + " end"
    assert extract_urls(text) == {"http://evil.example/a[" + "x" * 4000}


# --- Obfuscation-resistant matching: the encoded defang separator, punycode, and zero-width format
# characters (ADR-0015 seventh addendum). The separator anchors the match and so is matched before
# any decode, but only its *shape* need be constrained: a bracket chunk carrying an escape marker
# (`&`/`%`) is admitted and `normalize_url`'s decode fixpoint resolves whichever encoding it was,
# so
# no table of encodings enters the anchor. Punycode decoding (stdlib `idna`) feeds the confusable
# table a registered IDN homoglyph, and Cf-category characters, which survive NFKC, are stripped. -


def test_extract_urls_refangs_an_encoded_scheme_separator() -> None:
    # The gap: the colon entity-/percent-encoded inside defang brackets. The whole match used to
    # fail to anchor, so `extract_urls` returned *nothing*: both redact and strict mode missed it.
    plain = {"http://evil.example"}
    assert extract_urls("http[&#58;//]evil.example") == plain  # numeric entity colon
    assert extract_urls("http[%3a//]evil.example") == plain  # percent-escaped colon
    assert extract_urls("http(&#58;//)evil.example") == plain
    assert extract_urls("http{&#58;//}evil.example") == plain


def test_extract_urls_refangs_an_encoded_separator_on_an_opaque_scheme() -> None:
    assert extract_urls("mailto[&#58;]a@evil.example") == {"mailto:a@evil.example"}
    assert extract_urls("tel[%3a]+15550100") == {"tel:+15550100"}


def test_extract_urls_refangs_an_encoded_separator_on_a_data_url() -> None:
    # `data:` shares `_family`, so it inherits the encoded separator behind its MIME anchor.
    assert extract_urls("data[&#58;]text/html;base64,AA") == {"data:text/html;base64,aa"}


def test_an_encoded_separator_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http[&#58;//]evil.example") == extract_urls("http://evil.example")


def test_encoded_separator_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http[&#58;//]evil.example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_an_encoded_separator() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to http[&#58;//]evil.example ") == f"go to {REDACTED_LINK} "


def test_encoded_separator_split_across_chunks_is_carried_not_lost() -> None:
    # An encoded separator is variable-length, so it cannot be enumerated into the hold-back's
    # scheme prefixes; `_OPEN_SEP_RE` holds the buffer while the separator chunk is still open.
    guard = _filter({"http://evil.example"})
    assert guard.feed("at http[&#5") == "at "
    assert guard.feed("8;//]evil.example ") == f"{REDACTED_LINK} "


def test_an_unescaped_bracket_at_the_separator_is_not_a_url() -> None:
    # The escape marker is load bearing: without it this chunk would match ordinary prose, which
    # strict mode would then redact out of the repo's own docs.
    assert extract_urls("http(s)-only endpoints") == frozenset()
    assert extract_urls("use http(s) or ftp(s) here") == frozenset()


def test_a_bracket_run_without_a_scheme_word_is_not_held() -> None:
    # `_OPEN_SEP_RE` anchors on a scheme word, so ordinary bracketed prose streams straight through.
    guard = _filter({EVIL})
    assert guard.feed("config [abc") == "config [abc"


# Punycode: `xn--e1awd7f` is the registered ASCII-compatible encoding of Cyrillic "epic"
# (U+0435 0440 0456 0441), which the curated confusable table then folds to the ASCII it imitates.
_PUNYCODE_EPIC = "http://xn--e1awd7f.example"


def test_extract_urls_decodes_punycode_then_folds_the_confusables() -> None:
    assert extract_urls(_PUNYCODE_EPIC) == {"http://epic.example"}


def test_a_punycode_host_and_its_ascii_twin_share_one_identity() -> None:
    assert extract_urls(_PUNYCODE_EPIC) == extract_urls("http://epic.example")


def test_a_malformed_punycode_label_is_left_verbatim() -> None:
    # The codec rejects it (incomplete punycode); the label stays as-is rather than raising, and
    # the identity is still symmetric on both sides of the defense.
    assert extract_urls("http://xn--zzzzzzzz.example") == {"http://xn--zzzzzzzz.example"}


def test_punycode_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://epic.example"})
    fed = guard.feed(f"see {_PUNYCODE_EPIC} now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_extract_urls_strips_zero_width_format_characters() -> None:
    # Cf-category characters render as nothing but survive NFKC, so they used to split the identity.
    plain = {"http://evil.example"}
    assert extract_urls("http://evi\u200bl.example") == plain  # zero-width space
    assert extract_urls("http://evi\u200dl.example") == plain  # zero-width joiner
    assert extract_urls("http://evi\u00adl.example") == plain  # soft hyphen
    assert extract_urls("http://evi\ufeffl.example") == plain  # BOM / zero-width no-break space


def test_an_encoded_zero_width_character_is_stripped_after_decoding() -> None:
    # The stripper runs after the decode fixpoint, so a percent-encoded ZWSP is exposed first.
    assert extract_urls("http://evi%E2%80%8Bl.example") == {"http://evil.example"}


def test_zero_width_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evi\u200bl.example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_zero_width_split_host() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to http://evi\u200bl.example ") == f"go to {REDACTED_LINK} "


def test_the_seventh_addendum_classes_compose() -> None:
    # An encoded separator, a punycode host, and a zero-width character in one link still fold to
    # the single identity its plain twin has: the passes chain rather than shadowing one another.
    assert extract_urls("http[&#58;//]xn--e1awd7f\u200b.example") == {"http://epic.example"}


def test_extract_urls_refangs_every_defang_bracket_shape_at_the_separator() -> None:
    # The standing asymmetry the seventh addendum found: the refanger folded `(.)`/`{.}` as readily
    # as `[.]`, but the separator tables listed only the square form, so a round- or brace-bracketed
    # separator anchored nothing and the link was never matched at all. All shapes are equivalent.
    plain = {"http://evil.example"}
    assert extract_urls("http(://)evil.example") == plain
    assert extract_urls("http{://}evil.example") == plain
    assert extract_urls("http(:)//evil.example") == plain
    assert extract_urls("http{:}//evil.example") == plain
    assert extract_urls("mailto(:)a@evil.example") == {"mailto:a@evil.example"}


def test_a_round_bracket_defang_separator_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http(://)evil.example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_a_bare_bracketed_colon_in_prose_is_not_a_url() -> None:
    # The separator only counts behind a scheme word, so ratio/emoticon prose is untouched.
    assert extract_urls("the ratio (:) here") == frozenset()


def test_an_opaque_turn_is_scanned_strictly_under_the_default_policy() -> None:
    """The default policy redacts URLs collected from untrusted result *text*. A URL painted
    into pixels is never in that text, so the collected set is empty and the default is
    structurally a no-op for exactly the laundering case vision introduces. Measured: the model
    transcribes the attacker URL out of the image verbatim, framed or not."""
    taint = _Taint(tainted=True, opaque=True)
    guard = UrlRedactingGuardrail().open(taint, allow=frozenset())
    fed = guard.feed(f"the screen says {EVIL} ") + guard.flush()
    assert EVIL not in fed
    assert REDACTED_LINK in fed


def test_a_tainted_but_transparent_turn_keeps_the_default_policy() -> None:
    """The control arm: without the opaque bit the same turn redacts only what it collected, so
    the escalation above is the bit and not some blanket tightening."""
    taint = _Taint(tainted=True, opaque=False)
    guard = UrlRedactingGuardrail().open(taint, allow=frozenset())
    fed = guard.feed(f"the page says {EVIL} ") + guard.flush()
    assert fed == f"the page says {EVIL} "


def test_an_opaque_turn_still_lets_a_url_the_user_sent_through() -> None:
    taint = _Taint(tainted=True, opaque=True)
    guard = UrlRedactingGuardrail().open(taint, allow=frozenset({EVIL}))
    fed = guard.feed(f"you asked about {EVIL} ") + guard.flush()
    assert fed == f"you asked about {EVIL} "


# --- Obfuscation-resistant matching: a URL spelled in the fullwidth and CJK twins of its own
# punctuation (ADR-0015 eighth addendum). Two gaps, both measured against the shipped module first.
# The matcher runs before any normalization, so a fullwidth scheme separator (U+FF1A colon, U+FF0F
# solidus) anchored nothing and the URL matched nothing at all: neither mode redacted it. And NFKC
# maps the halfwidth ideographic stop (U+FF61) onto U+3002 rather than to a dot, so a CJK-dotted
# host kept a second identity that the default (verbatim) policy missed while strict mode caught it.
# Unlike a defang, the reader decodes nothing here: the stdlib's own IDNA codec resolves a U+3002
# stop to a plain dot. Fixtures carry the literal glyph under test, so each takes the deliberate
# ambiguous-unicode noqa the fullwidth-homoglyph tests above established. -


def test_extract_urls_folds_the_idna_label_separators() -> None:
    plain = {"https://evil.example/pay"}
    assert extract_urls("https://evil。example/pay") == plain  # U+3002 ideographic full stop
    assert extract_urls("https://evil｡example/pay") == plain  # U+FF61, NFKC maps it to U+3002
    assert extract_urls("https://evil．example/pay") == plain  # noqa: RUF001  # U+FF0E, NFKC


def test_a_cjk_dotted_host_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("https://evil。example/pay") == extract_urls("https://evil.example/pay")


def test_a_cjk_dot_transform_of_a_collected_url_is_redacted() -> None:
    # The gap this closes is in the *default* policy: the respelling used to carry an identity the
    # collected set did not hold, so only strict mode (which flags every non-user URL) caught it.
    guard = _filter({"https://evil.example/pay"})
    fed = guard.feed("settle at https://evil。example/pay now") + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_extract_urls_anchors_a_fullwidth_scheme_separator() -> None:
    # Every combination of the two colons and the two solidi, since the separator is generated from
    # those tables rather than listed: a mixed spelling must not be the one nobody remembered.
    plain = {"https://evil.example/pay"}
    assert extract_urls("https：//evil.example/pay") == plain  # noqa: RUF001
    assert extract_urls("https:／／evil.example/pay") == plain  # noqa: RUF001
    assert extract_urls("https：／／evil.example/pay") == plain  # noqa: RUF001
    assert extract_urls("https:/／evil.example/pay") == plain  # noqa: RUF001


def test_a_fullwidth_separator_anchors_an_opaque_scheme_and_a_data_url() -> None:
    assert extract_urls("mailto：a@evil.example") == {"mailto:a@evil.example"}  # noqa: RUF001
    assert extract_urls("tel：+15550100") == {"tel:+15550100"}  # noqa: RUF001
    assert extract_urls("data：text/html;base64,AA") == {"data:text/html;base64,aa"}  # noqa: RUF001


def test_a_fullwidth_separator_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http：//evil.example now") + guard.flush()  # noqa: RUF001
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_fullwidth_separator() -> None:
    # The worse half of this gap: an unanchored URL is invisible to strict mode too, which is
    # otherwise the policy that catches every rewrite the verbatim one misses.
    guard = _strict(_Taint(tainted=True))
    fed = guard.feed("go to http：//evil.example ")  # noqa: RUF001
    assert fed == f"go to {REDACTED_LINK} "


def test_a_fullwidth_separator_split_across_chunks_is_carried_not_lost() -> None:
    # The streaming hold-back derives its scheme prefixes from the same separator tables, so a
    # fullwidth spelling split across deltas is held rather than leaked in pieces.
    guard = _filter({"http://evil.example"})
    assert guard.feed("at http：") == "at "  # noqa: RUF001
    assert guard.feed("//evil.example ") == f"{REDACTED_LINK} "


def test_a_fullwidth_colon_without_a_scheme_word_is_not_a_url() -> None:
    # The separator counts only behind a scheme word, so CJK prose (where the fullwidth colon is
    # ordinary punctuation) streams through untouched, and an authority scheme still needs slashes.
    assert extract_urls("項目：内容") == frozenset()  # noqa: RUF001
    assert extract_urls("https：no slashes here") == frozenset()  # noqa: RUF001


def test_the_eighth_addendum_classes_compose() -> None:
    # A fullwidth separator and a CJK-dotted host in one link still fold to the plain identity.
    assert extract_urls("https：//evil。example/pay") == {"https://evil.example/pay"}  # noqa: RUF001


# --- Obfuscation-resistant matching: a scheme separator spelled as a *bracketless* HTML character
# reference (ADR-0015 ninth addendum). `https&#58;//evil.example` anchored nothing, so neither
# policy saw it: the encoded separator the seventh addendum admitted needed defang brackets around
# it, and the eighth addendum's tables held only glyphs. An HTML renderer resolves the reference
# before anything looks for a URL, which is what puts this class on the closed side of the line the
# eighth addendum drew, so the whole *family* is generated from each separator character's
# codepoint: decimal and hexadecimal, zero-padded or not, semicolon or not, plus the named form. -

_ENTITY_LINK = "https&#58;//evil.example/pay"
_PLAIN_LINK = {"https://evil.example/pay"}


def test_extract_urls_anchors_an_entity_spelled_colon() -> None:
    # Every numeric spelling of one colon, since the family is generated from the codepoint rather
    # than listed: a padding or a casing nobody thought of must not be the one that gets through.
    assert extract_urls(_ENTITY_LINK) == _PLAIN_LINK
    assert extract_urls("https&#058;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#0058;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#58//evil.example/pay") == _PLAIN_LINK  # HTML makes the `;` optional
    assert extract_urls("https&#x3a;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#X3A;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#x003a;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&colon;//evil.example/pay") == _PLAIN_LINK


def test_extract_urls_anchors_an_entity_spelled_solidus() -> None:
    # The solidus is generated from the same table, so it and the colon mix freely with each other
    # and with the fullwidth glyphs the eighth addendum admitted.
    assert extract_urls("https:&#47;&#47;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:&sol;&sol;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#58;&#47;&#47;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#58;／／evil.example/pay") == _PLAIN_LINK  # noqa: RUF001
    assert extract_urls("https&colon;&#x2f;／evil.example/pay") == _PLAIN_LINK  # noqa: RUF001


def test_an_entity_separator_anchors_an_opaque_scheme_and_a_data_url() -> None:
    assert extract_urls("mailto&#58;a@evil.example") == {"mailto:a@evil.example"}
    assert extract_urls("tel&colon;+15550100") == {"tel:+15550100"}
    assert extract_urls("data&#x3a;text/html;base64,AA") == {"data:text/html;base64,aa"}


def test_an_entity_separator_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls(_ENTITY_LINK) == extract_urls("https://evil.example/pay")


def test_an_entity_separator_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"https://evil.example/pay"})
    fed = guard.feed(f"settle at {_ENTITY_LINK} now") + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_an_entity_separator() -> None:
    # The severe half again: a link that anchors nothing is invisible to strict mode too, which is
    # otherwise the backstop for every rewrite the verbatim policy misses.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"go to {_ENTITY_LINK} ") == f"go to {REDACTED_LINK} "


def test_an_entity_separator_split_across_chunks_is_carried_not_lost() -> None:
    # A reference is variable-length, so like the bracketed chunk it cannot be enumerated into the
    # hold-back's scheme prefixes; the buffer is held while one is unfinished, at any split point.
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https&#5") == "at "
    assert guard.feed("8;&#4") == ""
    assert guard.feed("7;/evil.example/pay ") == f"{REDACTED_LINK} "


def test_an_entity_separator_survives_a_one_character_stream() -> None:
    # The production shape: the filter sees one character at a time, so a fix that only works on a
    # whole delta is wrong where it matters.
    guard = _filter({"https://evil.example/pay"})
    reply = f"settle at {_ENTITY_LINK} now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_an_entity_colon_in_prose_is_not_a_url() -> None:
    # The scheme word and (for an authority scheme) both solidi are still required, so prose that
    # merely spells a colon or a slash, and a scheme word beside an unrelated reference, stay out.
    assert extract_urls("write &#58; for a colon and &sol; for a slash") == frozenset()
    assert extract_urls("see the http&colon; spelling in the docs") == frozenset()
    assert extract_urls("the data&nbsp;table below") == frozenset()


def test_a_reference_no_renderer_resolves_is_not_admitted() -> None:
    # The line this addendum draws is *one rendering pass*. HTML named references are
    # case-sensitive, so `&COLON;` renders as itself and is not a link; a semicolon-less numeric
    # reference ends where its digit (or hex digit) run does, so `&#58123` is one five-digit
    # reference and renders as a private-use character rather than a colon; and `&amp;#58;` renders
    # as the *text* `&#58;`, which is still not a clickable link.
    assert extract_urls("https&COLON;//evil.example/pay") == frozenset()
    assert extract_urls("mailto&#58123@evil.example") == frozenset()
    assert extract_urls("tel&#x3abc") == frozenset()
    assert extract_urls("https&amp;#58;//evil.example/pay") == frozenset()
    # The same references *with* their semicolon are colons again, so the guard is a boundary and
    # not a ban on the shape.
    assert extract_urls("mailto&#58;123@evil.example") == {"mailto:123@evil.example"}


def test_the_ninth_addendum_composes_with_its_predecessors() -> None:
    # An entity colon, a fullwidth solidus, a CJK-dotted host and a zero-width character in one
    # link still fold to the single identity its plain twin has.
    assert extract_urls("https&#58;/／evil。ex\u200bample/pay") == _PLAIN_LINK  # noqa: RUF001


# --- Obfuscation-resistant matching: a backslash where a special scheme takes a solidus (ADR-0015
# tenth addendum). `https:\/\/evil.example/pay`, the JSON-escaped spelling of a link and the shape a
# regex literal writes, anchored nothing, so neither policy saw it. Like the CJK stop and unlike a
# source-code escape, the reader decodes nothing: the URL Standard's special-authority states skip
# `/` and `\` alike, so a parser reads the spelling as the plain link. The solidus table gained the
# character and the identity gained the fold, so the path position and the entity references of a
# backslash (`&#92;`, `&bsol;`) come with it. -


def test_extract_urls_anchors_a_backslash_spelled_separator() -> None:
    # Every mixture of the two characters, since the separator is generated from the table: the
    # JSON-escaped pair writes four characters where two are expected, and the run folds to a pair.
    assert extract_urls(r"https:\/\/evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"https:\\evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"https:/\evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:////evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"hxxp:\/\/evil.example/pay") == {"http://evil.example/pay"}


def test_extract_urls_anchors_an_entity_spelled_backslash() -> None:
    # References are generated for every character HTML names, not only the first in the table, so
    # the backslash carries its own family and mixes with the colon's and with the fullwidth glyphs.
    assert extract_urls("https:&#92;&#92;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:&#x5c;&#092;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:&bsol;&bsol;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#58;&bsol;\uff0fevil.example/pay") == _PLAIN_LINK


def test_a_backslash_in_the_path_folds_like_the_separator() -> None:
    # The parser's rule is not about the separator: in a special scheme's URL every backslash is a
    # solidus, so a path written with one has always matched but carried a second identity.
    assert extract_urls("https://evil.example\\pay") == _PLAIN_LINK
    assert extract_urls("https:\\\\evil.example\\pay") == _PLAIN_LINK


def test_a_backslash_separator_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls(r"https:\/\/evil.example/pay") == extract_urls("https://evil.example/pay")


def test_a_backslash_transform_of_a_collected_url_is_redacted() -> None:
    # The default policy's half of the gap: the respelling used to carry no identity at all, so a
    # link collected plainly from untrusted content came back through it unredacted.
    guard = _filter({"https://evil.example/pay"})
    fed = guard.feed(r"settle at https:\/\/evil.example/pay now") + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_backslash_separator() -> None:
    # The severe half a third time: a spelling that anchors nothing is invisible to strict mode too.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(r"go to https:\/\/evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_a_backslash_separator_split_across_chunks_is_carried_not_lost() -> None:
    # The hold-back's scheme prefixes are concatenated from the same tables, so the backslash
    # spellings are carried across deltas exactly as the fullwidth ones are.
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https:\\") == "at "
    assert guard.feed("/evil.example/pay ") == f"{REDACTED_LINK} "


def test_a_backslash_separator_survives_a_one_character_stream() -> None:
    # The production shape, for the entity spelling too: the filter sees one character at a time.
    guard = _filter({"https://evil.example/pay"})
    reply = "settle at https:&bsol;&#92;evil.example/pay now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_a_backslash_no_parser_reads_as_a_solidus_is_not_folded() -> None:
    # The fold is the parser's rule and carries that rule's scope with it: an opaque scheme is not
    # a special one, so `mailto:`/`tel:`/`data:` keep their backslashes; a scheme word is still
    # required, so a Windows path is no link; and the named reference is still case-sensitive.
    assert extract_urls("mailto:a\\b@evil.example") == {"mailto:a\\b@evil.example"}
    assert extract_urls("C:\\Users\\me\\report.txt") == frozenset()
    assert extract_urls("escape a backslash as &bsol; in HTML") == frozenset()
    assert extract_urls("https&BSOL;//evil.example/pay") == frozenset()
    assert extract_urls("https:\\ nothing here") == frozenset()


def test_a_source_escape_folds_to_the_host_a_parser_reads_it_as() -> None:
    # The rows this addendum declines, pinned by what makes them a decline: a parser hands the
    # backslash to the path, so the escape names the host `evil` and never the collected link.
    # The identity now says exactly that, which is why folding the backslash does not admit them.
    assert extract_urls(r"https://evil\u002eexample/pay") == {"https://evil/u002eexample/pay"}
    assert extract_urls(r"https://evil\x2eexample/pay") == {"https://evil/x2eexample/pay"}
    assert extract_urls(r"https://evil\.example/pay") == {"https://evil/.example/pay"}
    assert extract_urls("https%3A//evil.example/pay") == frozenset()


def test_the_tenth_addendum_composes_with_its_predecessors() -> None:
    # An entity colon, a backslash separator, a CJK-dotted host and a zero-width character in one
    # link still fold to the single identity its plain twin has.
    assert extract_urls("https&#58;\\/evil\u3002ex\u200bample/pay") == _PLAIN_LINK


# --- Obfuscation-resistant matching: a special scheme's authority spelled with fewer than two
# solidi (ADR-0015 eleventh addendum). `https:evil.example/pay` and `https:/evil.example/pay` are
# both `https://evil.example/pay` to a URL parser, because the special-authority states that skip a
# backslash tolerate a missing one, so the matcher's demand for both solidi let a live link anchor
# nothing. Every widening before this constrained the spelling of a separator that was there; this
# one admits a separator that is absent, so the anchor asks instead what follows it to look like a
# host, which a dot or a bracketed colon says and an English word does not. --------------------


def test_extract_urls_anchors_a_slashless_authority() -> None:
    # The bypass: one solidus or none, in every scheme the parser reads a special authority for.
    assert extract_urls("https:evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:/evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"https:\evil.example/pay") == _PLAIN_LINK
    assert extract_urls("http:evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("hxxp:evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("ftp:evil.example/pay") == {"ftp://evil.example/pay"}


def test_a_slashless_authority_takes_every_separator_spelling() -> None:
    # The position inherits the tables rather than growing a second one, so the entity colon and
    # the fullwidth twin the earlier addenda landed reach the slashless form for free.
    assert extract_urls("https&#58;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&colon;/evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https：evil.example/pay") == _PLAIN_LINK  # noqa: RUF001
    assert extract_urls("https:&#92;evil.example/pay") == _PLAIN_LINK


def test_a_defanged_colon_reaches_the_slashless_form_too() -> None:
    # The separator families cannot part company at this position either: a bare defanged colon
    # spells the same missing solidi, and the refanger already turned it back into one. Leaving it
    # out would have been the seventh addendum's bracket asymmetry over again, and the *encoded*
    # chunk had reached here on its own all along, since its branch never asked for a solidus.
    assert extract_urls("http[:]evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("http(:)/evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("http{:}evil.example/pay") == {"http://evil.example/pay"}
    guard = _filter({"http://evil.example/pay"})
    assert guard.feed("at http[:]evil.") == "at "
    assert guard.feed("example/pay ") == f"{REDACTED_LINK} "


def test_a_slashless_authority_and_its_plain_twin_share_one_identity() -> None:
    # The identity folds an *empty* run of authority slashes now, not just a mis-spelled one.
    assert extract_urls("https:evil.example/pay") == extract_urls("https://evil.example/pay")
    assert extract_urls("https:evil.example") == extract_urls("https://evil.example")


def test_a_slashless_transform_of_a_collected_url_is_redacted() -> None:
    # The default policy's half of the gap: dropping a solidus carried no identity at all, so a
    # link collected plainly from untrusted content came back through it unredacted.
    guard = _filter({"https://evil.example/pay"})
    fed = guard.feed("settle at https:evil.example/pay now") + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_slashless_authority() -> None:
    # The severe half a sixth time: a spelling that anchors nothing is invisible to strict mode too.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to https:evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_a_slashless_authority_split_across_chunks_is_carried_not_lost() -> None:
    # The host is what anchors this form, so a buffer ending mid-host is not yet a match and is not
    # yet a scheme prefix either; the hold-back carries a scheme word whose host is still arriving.
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https:evil.") == "at "
    assert guard.feed("example/pay ") == f"{REDACTED_LINK} "


def test_a_slashless_authority_survives_a_one_character_stream() -> None:
    # The production shape: the filter sees one character at a time.
    guard = _filter({"https://evil.example/pay"})
    reply = "settle at https:/evil.example/pay now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_a_dotted_host_is_what_a_dot_of_any_reading_spells() -> None:
    # The anchor's dot is the resolver's, not ASCII's: the label separators IDNA splits a host on
    # come from the same table the identity folds, and a rendered reference is a dot by the ninth
    # addendum's own rule, so the classes compose in the position that now needs a host.
    assert extract_urls("https:evil。example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil｡example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil．example/pay") == _PLAIN_LINK  # noqa: RUF001
    assert extract_urls("https:evil&#46;example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil&period;example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil%2eexample/pay") == _PLAIN_LINK
    # And the readings the parser does not have: it decodes a host once, refusing the
    # stacked escape, and a label with nothing after it is the single label declined below.
    assert extract_urls("https:evil%252eexample/pay") == frozenset()
    assert extract_urls("https:evil./pay") == frozenset()


def test_a_port_userinfo_and_the_literal_hosts_are_all_host_shaped() -> None:
    # Everything a host can be that carries a dot rides on the dot, userinfo and a port included
    # since both sit outside the name; an IPv6 literal has no dot and is admitted on its brackets.
    assert extract_urls("https:evil.example:8443/pay") == {"https://evil.example:8443/pay"}
    assert extract_urls("https:user:pw@evil.example/pay") == {"https://user:pw@evil.example/pay"}
    assert extract_urls("https:127.0.0.1/pay") == {"https://127.0.0.1/pay"}
    assert extract_urls("https:[::1]/pay") == {"https://[::1]/pay"}
    assert extract_urls("https:bücher.example/pay") == {"https://bücher.example/pay"}


def test_a_single_label_authority_is_the_false_positive_budget_and_stays_out() -> None:
    # The whole cost of admitting an absent separator, paid where prose lives. A scheme word, a
    # colon and one English word is a live URL to a parser (`https:scheme` is `https://scheme/`),
    # and it is also how a sentence names a scheme, so the anchor declines every single-label host.
    # Nothing public resolves there anyway: a bare label is registrable under no public suffix.
    assert extract_urls("the https: scheme is the one to use") == frozenset()
    assert extract_urls("see https: for the scheme") == frozenset()
    assert extract_urls("the scheme is https:") == frozenset()
    assert extract_urls("https:no slashes here") == frozenset()
    assert extract_urls("https:scheme") == frozenset()
    assert extract_urls("reach it at https:localhost:8080/x") == frozenset()
    assert extract_urls("http:foo and ftp:bar") == frozenset()


def test_prose_after_a_scheme_colon_still_streams_through() -> None:
    # The hold-back may carry a scheme word whose host is still arriving, but carrying is not
    # redacting: prose that never becomes a host is released whole, in order, by the flush.
    guard = _strict(_Taint(tainted=True))
    reply = "the https: scheme, or https:scheme without the space"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == reply


def test_a_non_special_scheme_reads_its_colon_exactly_as_before() -> None:
    # The widening is the parser's rule and carries that rule's scope: only a *special* scheme has
    # an authority to find, so an opaque one keeps its opaque reading and an unlisted one is still
    # no link at all.
    assert extract_urls("mailto:evil.example") == {"mailto:evil.example"}
    assert extract_urls("data:evil.example") == frozenset()
    assert extract_urls("javascript:evil.example") == frozenset()
    assert extract_urls("tel:1.800.555.0100") == {"tel:1.800.555.0100"}


def test_the_eleventh_addendum_composes_with_its_predecessors() -> None:
    # An entity colon, a single backslash for the missing solidus, a CJK-dotted host and a
    # zero-width character in one link still fold to the single identity its plain twin has.
    assert extract_urls("https&#58;\\evil。ex\u200bample/pay") == _PLAIN_LINK


_SPLIT_HOST = "hxxps://evil dot example/pay"


def test_extract_urls_reads_a_whitespace_split_host() -> None:
    # The last member of the defang family, and the one the security community writes as readily
    # as `evil[.]com`. The gap between two labels is the host's dot, so the split spelling folds
    # to the identity its plain twin has and neither side of the defense can miss the other.
    assert extract_urls(_SPLIT_HOST) == _PLAIN_LINK
    assert extract_urls("http://evil dot example") == {"http://evil.example"}
    assert extract_urls("ftp://evil dot example/x") == {"ftp://evil.example/x"}
    assert extract_urls("http://a dot b dot c dot example") == {"http://a.b.c.example"}


def test_a_gap_may_hold_any_reading_of_the_dot() -> None:
    # The gap's token comes from the same tables every other position spends, so the word, each
    # label separator, a rendered reference, one percent escape and the refanger's own bracketed
    # token all reach this position without being listed here or there.
    for spelling in ("dot", "DOT", ".", "。", "&#46;", "&period;", "%2e", "[dot]", "(.)", "{DOT}"):
        assert extract_urls(f"https://evil {spelling} example/pay") == _PLAIN_LINK
    # Tabs and runs of whitespace are the same gap; a newline is not, being where a wrapped
    # sentence breaks rather than where a host's label does.
    assert extract_urls("https://evil \t dot \t example/pay") == _PLAIN_LINK
    assert extract_urls("https://evil\ndot example/pay") == {"https://evil"}


def test_a_dotted_host_is_finished_before_any_gap_could_join_it() -> None:
    # The whole false-positive budget, and the constraint the rest of it rests on: defanging
    # *replaces* a host's dot and never adds one, so a host that already carries a plain dot ends
    # where it always did. Without it a `+` body loop re-enters the split host at every position
    # and reads an ordinary link plus the next two words as one, which is measured, not feared.
    assert extract_urls("visit http://example.com dot the file is there") == {"http://example.com"}
    assert extract_urls("see http://example.com . The next sentence") == {"http://example.com"}
    assert extract_urls("the report is at http://example.com dot org") == {"http://example.com"}


def test_an_unanchored_split_host_is_still_no_link() -> None:
    # The fragment's own spelling with no scheme in front of it stays out, on the standing
    # decision that puts its plain twin out: `evil.example` is not a link here either, and a
    # grammar that redacted the split form while ignoring the contiguous one would be incoherent.
    assert extract_urls("evil dot example") == frozenset()
    assert extract_urls("evil . example") == frozenset()
    assert extract_urls("mail me at evil dot example") == frozenset()


def test_only_an_authority_scheme_has_a_host_to_split() -> None:
    # A split host is a *host* grammar, and only these schemes have one. An opaque scheme reaches
    # its content through a colon and no authority, so its content is read exactly as before and
    # a `tel:` number is never held waiting for a gap that cannot come.
    assert extract_urls("mailto:me dot you") == {"mailto:me"}
    assert extract_urls("tel:555 dot 0100") == {"tel:555"}
    assert extract_urls("data:text/html,hi dot there") == {"data:text/html,hi"}


def test_a_gap_needs_a_label_on_both_sides() -> None:
    # A gap separates two labels, so it is not one with nothing before it or nothing after it,
    # and the token must stand alone rather than sit inside a word.
    assert extract_urls("http:// dot example") == frozenset()
    assert extract_urls("http://evil dot ") == {"http://evil"}
    assert extract_urls("http://evil dotexample") == {"http://evil"}
    assert extract_urls("http://evildot example") == {"http://evildot"}


def test_only_the_host_is_split_never_the_path() -> None:
    # The gap belongs to the authority; past it the ordinary body resumes, so a space in a path
    # ends the match exactly as it always has.
    assert extract_urls("http://evil dot example/a b") == {"http://evil.example/a"}
    assert extract_urls("http://evil dot example?q=1") == {"http://evil.example?q=1"}


def test_a_split_transform_of_a_collected_url_is_redacted() -> None:
    # Both directions, because a mismatch of identities leaks whichever side spells it oddly.
    # Untrusted content that wrote its link split put a *wrong* host in the ledger before this
    # (`http://evil`), so the plain link in the reply went unredacted too.
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed(f"go to {_SPLIT_HOST} ") == f"go to {REDACTED_LINK} "
    plain = _filter(set(extract_urls(_SPLIT_HOST)))
    assert plain.feed("go to https://evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_a_split_host_leaves_no_host_beside_the_marker() -> None:
    # The third failure shape this closes, past "leaked" and "wrong identity": a redaction that
    # stopped at the first gap replaced the scheme and left the attacker's host standing next to
    # the marker, which reads as a redaction while still delivering the host.
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"Please visit {_SPLIT_HOST} now.") == f"Please visit {REDACTED_LINK} now."


def test_strict_tainted_turn_redacts_a_split_host() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"see {_SPLIT_HOST} ") == f"see {REDACTED_LINK} "


def test_a_split_host_arriving_across_chunks_is_carried_not_lost() -> None:
    # A gap that has opened but not closed is neither a match nor a prefix of any scheme, so the
    # hold-back carries the dotless host it sits behind rather than releasing its head one delta
    # before the gap closes.
    for tail in (" ", " d", " do", " dot", " dot ", " [do", " &#4", " %2"):
        guard = _filter({"https://evil.example/pay"})
        assert guard.feed(f"at https://evil{tail}") == "at "
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https://evil dot ") == "at "
    assert guard.feed("example/pay ") == f"{REDACTED_LINK} "


def test_prose_after_a_dotless_host_still_streams_through() -> None:
    # Carrying is not redacting, and the carry is bounded: a word no gap could open with is
    # released at once, and an ordinary link followed by a space is untouched, which is what
    # keeps this branch off every URL in every reply.
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https://other now") == "at https://other now"
    assert guard.feed("at https://ok.example/x ") == "at https://ok.example/x "


def test_a_split_host_survives_a_one_character_stream() -> None:
    # The production shape: the filter sees one character at a time.
    guard = _filter({"https://evil.example/pay"})
    reply = f"settle at {_SPLIT_HOST} now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_the_twelfth_addendum_composes_with_its_predecessors() -> None:
    # A defanged scheme, an entity-spelled gap, a CJK stop in the next gap and a zero-width
    # character in one link still fold to the single identity its plain twin has.
    assert extract_urls("hxxps://ev\u200bil &#46; example/pay") == _PLAIN_LINK
    assert extract_urls("hxxps://evil [dot] ex\u3002ample/pay") == {"https://evil.ex.ample/pay"}
    # The one combination deliberately left out: a slashless authority *and* a split host at once.
    # The host anchor that admits an absent separator reads a dotted name, and a gap is not one.
    assert extract_urls("https:evil dot example/pay") == frozenset()


def test_a_gap_is_spelled_with_every_space_nfkc_folds() -> None:
    # A no-break, thin or ideographic space renders as a blank, so the reader sees exactly the
    # spelling above; the matcher runs before NFKC, so each of these anchored nothing at all.
    # The identity needs no table of its own, NFKC having reduced them before the fold runs.
    for space in ("\u00a0", "\u2009", "\u3000", "\u202f"):
        assert extract_urls(f"hxxps://evil{space}dot{space}example/pay") == _PLAIN_LINK
    assert extract_urls("hxxps://evil\u00a0dot\u2009example/pay") == _PLAIN_LINK


def test_the_gap_space_table_is_exactly_what_nfkc_folds_to_a_space() -> None:
    # The table is the claim, so the claim is checked against the database rather than trusted: a
    # later Unicode version adding a space character reddens here instead of quietly opening a gap.
    folded = {
        chr(point)
        for point in range(sys.maxunicode + 1)
        if chr(point) not in " \t" and unicodedata.normalize("NFKC", chr(point)) == " "
    }
    assert set(NFKC_SPACES) == folded


def test_whitespace_that_breaks_a_line_is_not_a_gap() -> None:
    # What NFKC leaves standing is the line-breaking family plus the Ogham space mark, which draws
    # a visible stroke. None of them is where a host's label breaks, and a newline is where a
    # wrapped sentence does, so a paragraph that happens to start with `dot` is not a host.
    for breaker in ("\n", "\r", "\u2028", "\u1680"):
        assert extract_urls(f"http://evil{breaker}dot{breaker}example") == {"http://evil"}
