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


def test_extract_urls_ignores_bare_domains_and_unsupported_schemes() -> None:
    # Bare domains and other schemes stay out of scope (ADR-0015): matching "setup.py"-shaped
    # prose or every bare "user@host" would over-redact.
    assert extract_urls("see evil.example or user@host.example or ftp://x.example") == frozenset()


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
