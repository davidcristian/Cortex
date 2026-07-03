"""Behavior tests for the output guardrail: URL extraction + the streaming redactor (ADR-0015)."""

from cortex_core import REDACTED_LINK, OutputFilter, UrlRedactingGuardrail, extract_urls

EVIL = "https://evil.example/report"


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


def test_extract_urls_ignores_bare_domains_and_other_schemes() -> None:
    # Out of scope by design (ADR-0015): matching "setup.py"-shaped prose would over-redact.
    assert extract_urls("see evil.example or mailto:a@b.example or ftp://x.example") == frozenset()


def test_extract_urls_empty_text_collects_nothing() -> None:
    assert extract_urls("") == frozenset()


def _filter(flagged: set[str], allow: frozenset[str] = frozenset()) -> OutputFilter:
    return UrlRedactingGuardrail().open(flagged, allow=allow)


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
