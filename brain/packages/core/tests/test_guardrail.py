"""Behavior tests for the output guardrail: URL extraction + the streaming redactor (ADR-0015)."""

from dataclasses import dataclass, field

from cortex_core import (
    REDACTED_LINK,
    OutputFilter,
    StrictUrlRedactingGuardrail,
    UrlRedactingGuardrail,
    extract_urls,
)

EVIL = "https://evil.example/report"


@dataclass
class _Taint:
    """A fake live ``TaintView``: the guardrail reads ``.tainted`` and ``.untrusted_urls`` at scan
    time. Both are mutable so a test can grow them mid-stream, exactly as the real ledger does."""

    tainted: bool = False
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
