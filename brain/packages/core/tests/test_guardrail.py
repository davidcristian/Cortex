import sys
import unicodedata
from dataclasses import dataclass, field

import pytest

from cortex_core import (
    REDACTED_LINK,
    LookalikeUrlRedactingGuardrail,
    OutputFilter,
    OutputGuardrail,
    StrictUrlRedactingGuardrail,
    UrlRedactingGuardrail,
    extract_urls,
)
from cortex_core.url_identity import host_of, normalize_url
from cortex_core.url_separators import NFKC_SPACES

EVIL = "https://evil.example/report"


@dataclass
class _Taint:
    """A fake ``TaintView``, read by the guardrail when it scans."""

    tainted: bool = False
    opaque: bool = False
    untrusted_urls: set[str] = field(default_factory=set[str])


def test_extract_urls_finds_every_absolute_web_url() -> None:
    text = f"see {EVIL} and http://phish.example/a?b=c#d for details"
    assert extract_urls(text) == {EVIL, "http://phish.example/a?b=c#d"}


def test_extract_urls_normalizes_scheme_and_host_but_not_the_path() -> None:
    assert extract_urls("HTTPS://EVIL.Example/Report?Q=CaSe") == {
        "https://evil.example/Report?Q=CaSe"
    }


def test_extract_urls_lowercases_a_bare_authority_whole() -> None:
    assert extract_urls("go to HTTPS://EVIL.EXAMPLE now") == {"https://evil.example"}


def test_extract_urls_drops_trailing_prose_punctuation() -> None:
    assert extract_urls(f"Visit {EVIL}.") == {EVIL}
    assert extract_urls(f"Really: {EVIL}!?") == {EVIL}


def test_extract_urls_ignores_bare_domains_and_addresses() -> None:
    assert extract_urls("see evil.example or user@host.example") == frozenset()


def test_extract_urls_collects_mailto_links_case_folded() -> None:
    text = "write a@b.example or click mailto:Abuse@Evil.Example?subject=Hi"
    assert extract_urls(text) == {"mailto:abuse@evil.example?subject=hi"}


def test_extract_urls_empty_text_collects_nothing() -> None:
    assert extract_urls("") == frozenset()


def _filter(flagged: set[str], allow: frozenset[str] = frozenset()) -> OutputFilter:
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
    # The trailing "h" could open "https://", so it is held until the next chunk shows it is prose.
    assert guard.feed("approach") == "approac"
    assert guard.feed(" works") == "h works"
    assert guard.flush() == ""


def test_bare_open_scheme_is_held_until_it_resolves() -> None:
    guard = _filter({EVIL})
    assert guard.feed("go to https://") == "go to "
    assert guard.feed("evil.example/report ") == f"{REDACTED_LINK} "


def test_live_set_growth_is_seen_by_a_later_feed() -> None:
    flagged: set[str] = set()
    guard = _filter(flagged)
    assert guard.feed(f"before {EVIL} ") == f"before {EVIL} "
    flagged.add(EVIL)
    assert guard.feed(f"after {EVIL} ") == f"after {REDACTED_LINK} "


_EVIL_MAIL = "mailto:attacker@evil.example"


def test_verbatim_mailto_link_is_redacted() -> None:
    guard = _filter({_EVIL_MAIL})
    assert guard.feed(f"contact {_EVIL_MAIL} now") + guard.flush() == (
        f"contact {REDACTED_LINK} now"
    )


def test_partial_mailto_scheme_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({"mailto:x@evil.example"})
    assert guard.feed("reach me at mailto") == "reach me at "
    assert guard.feed(":x@evil.example ") == f"{REDACTED_LINK} "


def test_strict_untainted_turn_passes_every_url() -> None:
    guard = _strict(_Taint(tainted=False))
    text = f"docs at https://docs.example and {EVIL}"
    assert guard.feed(text) + guard.flush() == text


def test_strict_tainted_turn_redacts_a_url_never_collected_verbatim() -> None:
    guard = _strict(_Taint(tainted=True))
    fabricated = "https://transformed.evil.example/x"
    assert guard.feed(f"see {fabricated} ") == f"see {REDACTED_LINK} "


def test_strict_tainted_turn_keeps_the_users_own_url() -> None:
    guard = _strict(_Taint(tainted=True), allow=frozenset({EVIL}))
    assert guard.feed(f"you sent {EVIL} ") == f"you sent {EVIL} "


def test_strict_tainted_turn_redacts_a_non_user_mailto() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("write mailto:x@evil.example ") == f"write {REDACTED_LINK} "


def test_extract_urls_refangs_a_defanged_scheme() -> None:
    assert extract_urls("hxxp://evil.example and hxxps://evil.example/a") == {
        "http://evil.example",
        "https://evil.example/a",
    }


def test_extract_urls_refangs_bracketed_dots() -> None:
    assert extract_urls("http://evil[.]example/a(.)b and http://x{.}y") == {
        "http://evil.example/a.b",
        "http://x.y",
    }


def test_extract_urls_refangs_the_word_dot_defang() -> None:
    assert extract_urls("http://evil[dot]example and http://a(DOT)b") == {
        "http://evil.example",
        "http://a.b",
    }


def test_extract_urls_refangs_bracketed_scheme_separators() -> None:
    assert extract_urls("http[://]evil.example and http[:]//evil.example/a") == {
        "http://evil.example",
        "http://evil.example/a",
    }


def test_extract_urls_refangs_a_defanged_mailto() -> None:
    assert extract_urls("mailto[:]abuse@evil[.]example") == {"mailto:abuse@evil.example"}


def test_a_defanged_url_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("hxxps://evil[.]example/report") == extract_urls(
        "https://evil.example/report"
    )


def test_extract_urls_refangs_only_the_leading_scheme_not_a_paths_hxx() -> None:
    assert extract_urls("http://ex.example/HxXp") == {"http://ex.example/HxXp"}


def test_extract_urls_still_ignores_a_defanged_host_without_a_scheme() -> None:
    assert extract_urls("reach evil[.]example or evil[dot]example") == frozenset()


def test_defang_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({EVIL})
    fed = guard.feed("see hxxps://evil[.]example/report now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_mode_redacts_a_defanged_link_that_used_to_escape() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to hxxp://evil[.]example ") == f"go to {REDACTED_LINK} "


def test_defanged_scheme_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({EVIL})
    assert guard.feed("report at hxx") == "report at "
    assert guard.feed("ps://evil[.]example/report ") == f"{REDACTED_LINK} "


def test_defanged_dot_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({EVIL})
    assert guard.feed("at https://evil[.") == "at "
    assert guard.feed("]example/report ") == f"{REDACTED_LINK} "


def test_extract_urls_percent_decodes_to_a_canonical_identity() -> None:
    assert extract_urls("http://evil%2eexample/re%70ort") == {"http://evil.example/report"}


def test_a_percent_encoded_url_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil%2eexample") == extract_urls("http://evil.example")


def test_percent_encoded_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({EVIL})
    fed = guard.feed("see https://evil%2eexample/report now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_extract_urls_folds_fullwidth_homoglyphs_to_ascii() -> None:
    assert extract_urls("http://ｅｖｉｌ．example") == {"http://evil.example"}  # noqa: RUF001


def test_fullwidth_homoglyph_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("go to http://ｅｖｉｌ.example ") + guard.flush()  # noqa: RUF001
    assert fed == f"go to {REDACTED_LINK} "


def test_extract_urls_matches_ftp_and_tel_schemes() -> None:
    text = "grab ftp://Files.Evil.Example/x and call tel:+1-555-0100"
    assert extract_urls(text) == {"ftp://files.evil.example/x", "tel:+1-555-0100"}


def test_scheme_words_only_match_at_a_word_boundary() -> None:
    assert extract_urls("check into hotel:room or use sftp://host.example") == frozenset()


def test_verbatim_ftp_link_is_redacted() -> None:
    evil_ftp = "ftp://files.evil.example/dump"
    guard = _filter({evil_ftp})
    assert guard.feed(f"exfil to {evil_ftp} ") + guard.flush() == f"exfil to {REDACTED_LINK} "


def test_strict_tainted_turn_redacts_a_non_user_tel() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("call tel:+1-555-0100 ") == f"call {REDACTED_LINK} "


def test_ftp_scheme_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({"ftp://files.evil.example"})
    assert guard.feed("grab it from ft") == "grab it from "
    assert guard.feed("p://files.evil.example ") == f"{REDACTED_LINK} "


def test_extract_urls_multipass_percent_decodes_to_a_canonical_identity() -> None:
    assert extract_urls("http://evil%252eexample") == {"http://evil.example"}


def test_a_double_encoded_url_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil%252eexample") == extract_urls("http://evil.example")


def test_multipass_percent_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evil%252eexample now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_percent_decoding_is_bounded_on_absurdly_deep_encoding() -> None:
    # The dot encoded six levels deep. Decoding stops after five passes, so it stays partly
    # encoded rather than being resolved further than a browser would.
    six_deep = "http://evil%25252525252eexample"
    assert extract_urls(six_deep) == {"http://evil%2eexample"}


# The Cyrillic letters U+0440 0430 0441 0435 render as "pace".
_CYRILLIC_PACE = "http://расе.example"  # noqa: RUF001


def test_extract_urls_folds_cyrillic_homoglyphs_to_ascii() -> None:
    assert extract_urls(_CYRILLIC_PACE) == {"http://pace.example"}


def test_a_homoglyph_host_and_its_ascii_twin_share_one_identity() -> None:
    assert extract_urls(_CYRILLIC_PACE) == extract_urls("http://pace.example")


def test_extract_urls_folds_uppercase_cyrillic_homoglyphs() -> None:
    # U+0421 041E are the Cyrillic letters that render as "CO".
    assert extract_urls("http://СО.example") == {"http://co.example"}  # noqa: RUF001


def test_extract_urls_folds_greek_homoglyphs() -> None:
    # U+03C1 03BF are the Greek letters rho and omicron, which render as "po".
    assert extract_urls("http://ρο.example") == {"http://po.example"}  # noqa: RUF001


def test_a_percent_encoded_homoglyph_folds_to_ascii() -> None:
    assert extract_urls("http://p%D0%B0ce.example") == {"http://pace.example"}


def test_cyrillic_homoglyph_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://pace.example"})
    fed = guard.feed(f"see {_CYRILLIC_PACE} now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_homoglyph_link() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"go to {_CYRILLIC_PACE} ") == f"go to {REDACTED_LINK} "


def test_extract_urls_decodes_html_entities_to_a_canonical_identity() -> None:
    plain = {"http://evil.example"}
    assert extract_urls("http://evil&#46;example") == plain
    assert extract_urls("http://evil&#x2e;example") == plain
    assert extract_urls("http://evil&period;example") == plain


def test_an_entity_encoded_url_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil&#46;example") == extract_urls("http://evil.example")


def test_entity_and_percent_encoding_compose_to_one_identity() -> None:
    assert extract_urls("http://evil&#37;2eexample") == {"http://evil.example"}


def test_entity_encoded_defang_brackets_are_refanged() -> None:
    assert extract_urls("http://evil&#91;.&#93;com") == {"http://evil.com"}


def test_entity_encoded_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evil&#46;example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


_DATA_URL = "data:text/html,hello"


def test_extract_urls_matches_a_data_url_with_a_mediatype() -> None:
    assert extract_urls(f"open {_DATA_URL} now") == {_DATA_URL}


def test_extract_urls_matches_a_data_url_with_an_immediate_comma() -> None:
    assert extract_urls("run data:,payload here") == {"data:,payload"}


def test_extract_urls_ignores_data_colon_in_prose() -> None:
    assert extract_urls("the data: shows a chart and data:the results vary") == frozenset()


def test_extract_urls_ignores_data_colon_in_prose_written_as_an_entity() -> None:
    text = "the data&#58; shows a chart and data&#58;the results vary"
    assert extract_urls(text) == frozenset()


def test_extract_urls_still_matches_an_entity_colon_before_a_real_mediatype() -> None:
    assert extract_urls("open data&#58;text/html,hello now") == {_DATA_URL}


def test_verbatim_data_url_is_redacted() -> None:
    guard = _filter({_DATA_URL})
    fed = guard.feed(f"see {_DATA_URL} now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_data_url() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"go to {_DATA_URL} ") == f"go to {REDACTED_LINK} "


def test_data_scheme_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({_DATA_URL})
    out = guard.feed("see data") + guard.feed(":text/html,hello now") + guard.flush()
    assert out == f"see {REDACTED_LINK} now"


def test_extract_urls_refangs_a_defang_dot_with_encoded_inner_and_literal_brackets() -> None:
    plain = {"http://evil.example"}
    assert extract_urls("http://evil[&#46;]example") == plain
    assert extract_urls("http://evil(&#46;)example") == plain
    assert extract_urls("http://evil{&#46;}example") == plain
    assert extract_urls("http://evil[%2e]example") == plain


def test_extract_urls_refangs_an_encoded_word_dot_behind_literal_brackets() -> None:
    assert extract_urls("http://evil[&#100;&#111;&#116;]example") == {"http://evil.example"}


def test_an_encoded_inner_defang_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("http://evil[&#46;]example") == extract_urls("http://evil.example")


def test_encoded_inner_defang_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evil[&#46;]example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_an_encoded_inner_defang() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to http://evil[&#46;]example ") == f"go to {REDACTED_LINK} "


def test_encoded_inner_defang_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({"http://evil.example"})
    assert guard.feed("at http://evil[&#46") == "at "
    assert guard.feed(";]example ") == f"{REDACTED_LINK} "


def test_empty_brackets_still_terminate_the_match_unchanged() -> None:
    assert extract_urls("http://api.example/tags[]=a") == {"http://api.example/tags["}


def test_a_parenthesized_url_still_bounds_at_the_closing_paren() -> None:
    assert extract_urls("(http://ex.example)") == {"http://ex.example"}


def test_a_bracketed_query_param_is_consumed_whole() -> None:
    assert extract_urls("http://api.example/s?a[0]=b") == {"http://api.example/s?a[0]=b"}


def test_a_long_unclosed_bracket_run_terminates_and_matches_linearly() -> None:
    text = "http://evil.example/a[" + "x" * 4000 + " end"
    assert extract_urls(text) == {"http://evil.example/a[" + "x" * 4000}


def test_extract_urls_refangs_an_encoded_scheme_separator() -> None:
    plain = {"http://evil.example"}
    assert extract_urls("http[&#58;//]evil.example") == plain
    assert extract_urls("http[%3a//]evil.example") == plain
    assert extract_urls("http(&#58;//)evil.example") == plain
    assert extract_urls("http{&#58;//}evil.example") == plain


def test_extract_urls_refangs_an_encoded_separator_on_an_opaque_scheme() -> None:
    assert extract_urls("mailto[&#58;]a@evil.example") == {"mailto:a@evil.example"}
    assert extract_urls("tel[%3a]+15550100") == {"tel:+15550100"}


def test_extract_urls_refangs_an_encoded_separator_on_a_data_url() -> None:
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
    guard = _filter({"http://evil.example"})
    assert guard.feed("at http[&#5") == "at "
    assert guard.feed("8;//]evil.example ") == f"{REDACTED_LINK} "


def test_an_unescaped_bracket_at_the_separator_is_not_a_url() -> None:
    assert extract_urls("http(s)-only endpoints") == frozenset()
    assert extract_urls("use http(s) or ftp(s) here") == frozenset()


def test_a_bracket_run_without_a_scheme_word_is_not_held() -> None:
    guard = _filter({EVIL})
    assert guard.feed("config [abc") == "config [abc"


# `xn--e1awd7f` is the punycode of the Cyrillic "epic" (U+0435 0440 0456 0441), which the
# confusable table then folds to the ASCII letters it imitates.
_PUNYCODE_EPIC = "http://xn--e1awd7f.example"


def test_extract_urls_decodes_punycode_then_folds_the_confusables() -> None:
    assert extract_urls(_PUNYCODE_EPIC) == {"http://epic.example"}


def test_a_punycode_host_and_its_ascii_twin_share_one_identity() -> None:
    assert extract_urls(_PUNYCODE_EPIC) == extract_urls("http://epic.example")


def test_a_malformed_punycode_label_is_left_verbatim() -> None:
    assert extract_urls("http://xn--zzzzzzzz.example") == {"http://xn--zzzzzzzz.example"}


def test_punycode_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://epic.example"})
    fed = guard.feed(f"see {_PUNYCODE_EPIC} now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_extract_urls_strips_zero_width_format_characters() -> None:
    plain = {"http://evil.example"}
    assert extract_urls("http://evi\u200bl.example") == plain
    assert extract_urls("http://evi\u200dl.example") == plain
    assert extract_urls("http://evi\u00adl.example") == plain
    assert extract_urls("http://evi\ufeffl.example") == plain


def test_an_encoded_zero_width_character_is_stripped_after_decoding() -> None:
    assert extract_urls("http://evi%E2%80%8Bl.example") == {"http://evil.example"}


def test_zero_width_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"http://evil.example"})
    fed = guard.feed("see http://evi\u200bl.example now") + guard.flush()
    assert fed == f"see {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_zero_width_split_host() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to http://evi\u200bl.example ") == f"go to {REDACTED_LINK} "


def test_the_encoded_separator_punycode_and_format_classes_compose() -> None:
    assert extract_urls("http[&#58;//]xn--e1awd7f\u200b.example") == {"http://epic.example"}


def test_extract_urls_refangs_every_defang_bracket_shape_at_the_separator() -> None:
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
    assert extract_urls("the ratio (:) here") == frozenset()


def test_an_opaque_turn_is_scanned_strictly_under_the_default_policy() -> None:
    taint = _Taint(tainted=True, opaque=True)
    guard = UrlRedactingGuardrail().open(taint, allow=frozenset())
    fed = guard.feed(f"the screen says {EVIL} ") + guard.flush()
    assert EVIL not in fed
    assert REDACTED_LINK in fed


def test_a_tainted_but_transparent_turn_keeps_the_default_policy() -> None:
    taint = _Taint(tainted=True, opaque=False)
    guard = UrlRedactingGuardrail().open(taint, allow=frozenset())
    fed = guard.feed(f"the page says {EVIL} ") + guard.flush()
    assert fed == f"the page says {EVIL} "


def test_an_opaque_turn_still_lets_a_url_the_user_sent_through() -> None:
    taint = _Taint(tainted=True, opaque=True)
    guard = UrlRedactingGuardrail().open(taint, allow=frozenset({EVIL}))
    fed = guard.feed(f"you asked about {EVIL} ") + guard.flush()
    assert fed == f"you asked about {EVIL} "


def test_extract_urls_folds_the_idna_label_separators() -> None:
    plain = {"https://evil.example/pay"}
    assert extract_urls("https://evil。example/pay") == plain
    assert extract_urls("https://evil｡example/pay") == plain
    assert extract_urls("https://evil．example/pay") == plain  # noqa: RUF001  # U+FF0E, NFKC


def test_a_cjk_dotted_host_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("https://evil。example/pay") == extract_urls("https://evil.example/pay")


def test_a_cjk_dot_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"https://evil.example/pay"})
    fed = guard.feed("settle at https://evil。example/pay now") + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_extract_urls_anchors_a_fullwidth_scheme_separator() -> None:
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
    guard = _strict(_Taint(tainted=True))
    fed = guard.feed("go to http：//evil.example ")  # noqa: RUF001
    assert fed == f"go to {REDACTED_LINK} "


def test_a_fullwidth_separator_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({"http://evil.example"})
    assert guard.feed("at http：") == "at "  # noqa: RUF001
    assert guard.feed("//evil.example ") == f"{REDACTED_LINK} "


def test_a_fullwidth_colon_without_a_scheme_word_is_not_a_url() -> None:
    assert extract_urls("項目：内容") == frozenset()  # noqa: RUF001
    assert extract_urls("https：no slashes here") == frozenset()  # noqa: RUF001


def test_the_fullwidth_punctuation_classes_compose() -> None:
    assert extract_urls("https：//evil。example/pay") == {"https://evil.example/pay"}  # noqa: RUF001


_ENTITY_LINK = "https&#58;//evil.example/pay"
_PLAIN_LINK = {"https://evil.example/pay"}


def test_extract_urls_anchors_a_colon_written_as_an_entity() -> None:
    assert extract_urls(_ENTITY_LINK) == _PLAIN_LINK
    assert extract_urls("https&#058;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#0058;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#58//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#x3a;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#X3A;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#x003a;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&colon;//evil.example/pay") == _PLAIN_LINK


def test_extract_urls_anchors_a_solidus_written_as_an_entity() -> None:
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
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"go to {_ENTITY_LINK} ") == f"go to {REDACTED_LINK} "


def test_an_entity_separator_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https&#5") == "at "
    assert guard.feed("8;&#4") == ""
    assert guard.feed("7;/evil.example/pay ") == f"{REDACTED_LINK} "


def test_an_entity_separator_survives_a_one_character_stream() -> None:
    guard = _filter({"https://evil.example/pay"})
    reply = f"settle at {_ENTITY_LINK} now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_an_entity_colon_in_prose_is_not_a_url() -> None:
    assert extract_urls("write &#58; for a colon and &sol; for a slash") == frozenset()
    assert extract_urls("see the http&colon; spelling in the docs") == frozenset()
    assert extract_urls("the data&nbsp;table below") == frozenset()


def test_a_reference_no_renderer_resolves_is_not_admitted() -> None:
    assert extract_urls("https&COLON;//evil.example/pay") == frozenset()
    assert extract_urls("mailto&#58123@evil.example") == frozenset()
    assert extract_urls("tel&#x3abc") == frozenset()
    assert extract_urls("https&amp;#58;//evil.example/pay") == frozenset()
    assert extract_urls("mailto&#58;123@evil.example") == {"mailto:123@evil.example"}


def test_the_entity_separator_composes_with_earlier_classes() -> None:
    assert extract_urls("https&#58;/／evil。ex\u200bample/pay") == _PLAIN_LINK  # noqa: RUF001


def test_extract_urls_anchors_a_separator_written_as_a_backslash() -> None:
    assert extract_urls(r"https:\/\/evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"https:\\evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"https:/\evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:////evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"hxxp:\/\/evil.example/pay") == {"http://evil.example/pay"}


def test_extract_urls_anchors_a_backslash_written_as_an_entity() -> None:
    assert extract_urls("https:&#92;&#92;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:&#x5c;&#092;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:&bsol;&bsol;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&#58;&bsol;\uff0fevil.example/pay") == _PLAIN_LINK


def test_a_backslash_in_the_path_folds_like_the_separator() -> None:
    assert extract_urls("https://evil.example\\pay") == _PLAIN_LINK
    assert extract_urls("https:\\\\evil.example\\pay") == _PLAIN_LINK


def test_a_backslash_separator_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls(r"https:\/\/evil.example/pay") == extract_urls("https://evil.example/pay")


def test_a_backslash_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"https://evil.example/pay"})
    fed = guard.feed(r"settle at https:\/\/evil.example/pay now") + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_backslash_separator() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(r"go to https:\/\/evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_a_backslash_separator_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https:\\") == "at "
    assert guard.feed("/evil.example/pay ") == f"{REDACTED_LINK} "


def test_a_backslash_separator_survives_a_one_character_stream() -> None:
    guard = _filter({"https://evil.example/pay"})
    reply = "settle at https:&bsol;&#92;evil.example/pay now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_a_backslash_no_parser_reads_as_a_solidus_is_not_folded() -> None:
    assert extract_urls("mailto:a\\b@evil.example") == {"mailto:a\\b@evil.example"}
    assert extract_urls("C:\\Users\\me\\report.txt") == frozenset()
    assert extract_urls("escape a backslash as &bsol; in HTML") == frozenset()
    assert extract_urls("https&BSOL;//evil.example/pay") == frozenset()
    assert extract_urls("https:\\ nothing here") == frozenset()


def test_a_source_escape_folds_to_the_host_a_parser_reads_it_as() -> None:
    assert extract_urls(r"https://evil\u002eexample/pay") == {"https://evil/u002eexample/pay"}
    assert extract_urls(r"https://evil\x2eexample/pay") == {"https://evil/x2eexample/pay"}
    assert extract_urls(r"https://evil\.example/pay") == {"https://evil/.example/pay"}
    assert extract_urls("https%3A//evil.example/pay") == frozenset()


def test_the_backslash_solidus_composes_with_earlier_classes() -> None:
    assert extract_urls("https&#58;\\/evil\u3002ex\u200bample/pay") == _PLAIN_LINK


def test_extract_urls_anchors_a_slashless_authority() -> None:
    assert extract_urls("https:evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https:/evil.example/pay") == _PLAIN_LINK
    assert extract_urls(r"https:\evil.example/pay") == _PLAIN_LINK
    assert extract_urls("http:evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("hxxp:evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("ftp:evil.example/pay") == {"ftp://evil.example/pay"}


def test_a_slashless_authority_takes_every_separator_form() -> None:
    assert extract_urls("https&#58;evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https&colon;/evil.example/pay") == _PLAIN_LINK
    assert extract_urls("https：evil.example/pay") == _PLAIN_LINK  # noqa: RUF001
    assert extract_urls("https:&#92;evil.example/pay") == _PLAIN_LINK


def test_a_defanged_colon_reaches_the_slashless_form_too() -> None:
    assert extract_urls("http[:]evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("http(:)/evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("http{:}evil.example/pay") == {"http://evil.example/pay"}
    guard = _filter({"http://evil.example/pay"})
    assert guard.feed("at http[:]evil.") == "at "
    assert guard.feed("example/pay ") == f"{REDACTED_LINK} "


def test_a_slashless_authority_and_its_plain_twin_share_one_identity() -> None:
    assert extract_urls("https:evil.example/pay") == extract_urls("https://evil.example/pay")
    assert extract_urls("https:evil.example") == extract_urls("https://evil.example")


def test_a_slashless_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"https://evil.example/pay"})
    fed = guard.feed("settle at https:evil.example/pay now") + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_strict_tainted_turn_redacts_a_slashless_authority() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("go to https:evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_a_slashless_authority_split_across_chunks_is_carried_not_lost() -> None:
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https:evil.") == "at "
    assert guard.feed("example/pay ") == f"{REDACTED_LINK} "


def test_a_slashless_authority_survives_a_one_character_stream() -> None:
    guard = _filter({"https://evil.example/pay"})
    reply = "settle at https:/evil.example/pay now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_a_dot_in_any_form_makes_a_dotted_host() -> None:
    assert extract_urls("https:evil。example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil｡example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil．example/pay") == _PLAIN_LINK  # noqa: RUF001
    assert extract_urls("https:evil&#46;example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil&period;example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil%2eexample/pay") == _PLAIN_LINK
    assert extract_urls("https:evil%252eexample/pay") == frozenset()
    assert extract_urls("https:evil./pay") == frozenset()


def test_a_port_userinfo_and_the_literal_hosts_are_all_host_shaped() -> None:
    assert extract_urls("https:evil.example:8443/pay") == {"https://evil.example:8443/pay"}
    assert extract_urls("https:user:pw@evil.example/pay") == {"https://user:pw@evil.example/pay"}
    assert extract_urls("https:127.0.0.1/pay") == {"https://127.0.0.1/pay"}
    assert extract_urls("https:[::1]/pay") == {"https://[::1]/pay"}
    assert extract_urls("https:bücher.example/pay") == {"https://bücher.example/pay"}


def test_a_single_label_authority_is_the_false_positive_budget_and_stays_out() -> None:
    assert extract_urls("the https: scheme is the one to use") == frozenset()
    assert extract_urls("see https: for the scheme") == frozenset()
    assert extract_urls("the scheme is https:") == frozenset()
    assert extract_urls("https:no slashes here") == frozenset()
    assert extract_urls("https:scheme") == frozenset()
    assert extract_urls("reach it at https:localhost:8080/x") == frozenset()
    assert extract_urls("http:foo and ftp:bar") == frozenset()


def test_prose_after_a_scheme_colon_still_streams_through() -> None:
    guard = _strict(_Taint(tainted=True))
    reply = "the https: scheme, or https:scheme without the space"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == reply


def test_a_non_special_scheme_reads_its_colon_exactly_as_before() -> None:
    assert extract_urls("mailto:evil.example") == {"mailto:evil.example"}
    assert extract_urls("data:evil.example") == frozenset()
    assert extract_urls("javascript:evil.example") == frozenset()
    assert extract_urls("tel:1.800.555.0100") == {"tel:1.800.555.0100"}


def test_the_slashless_authority_composes_with_earlier_classes() -> None:
    assert extract_urls("https&#58;\\evil。ex\u200bample/pay") == _PLAIN_LINK


_SPLIT_HOST = "hxxps://evil dot example/pay"


def test_extract_urls_reads_a_whitespace_split_host() -> None:
    assert extract_urls(_SPLIT_HOST) == _PLAIN_LINK
    assert extract_urls("http://evil dot example") == {"http://evil.example"}
    assert extract_urls("ftp://evil dot example/x") == {"ftp://evil.example/x"}
    assert extract_urls("http://a dot b dot c dot example") == {"http://a.b.c.example"}


def test_a_gap_may_hold_any_reading_of_the_dot() -> None:
    for form in ("dot", "DOT", ".", "。", "&#46;", "&period;", "%2e", "[dot]", "(.)", "{DOT}"):
        assert extract_urls(f"https://evil {form} example/pay") == _PLAIN_LINK
    assert extract_urls("https://evil \t dot \t example/pay") == _PLAIN_LINK
    assert extract_urls("https://evil\ndot example/pay") == {"https://evil"}


def test_a_dotted_host_is_finished_before_any_gap_could_join_it() -> None:
    assert extract_urls("visit http://example.com dot the file is there") == {"http://example.com"}
    assert extract_urls("see http://example.com . The next sentence") == {"http://example.com"}
    assert extract_urls("the report is at http://example.com dot org") == {"http://example.com"}


def test_an_unanchored_split_host_is_still_no_link() -> None:
    assert extract_urls("evil dot example") == frozenset()
    assert extract_urls("evil . example") == frozenset()
    assert extract_urls("mail me at evil dot example") == frozenset()


def test_only_an_authority_scheme_has_a_host_to_split() -> None:
    assert extract_urls("mailto:me dot you") == {"mailto:me"}
    assert extract_urls("tel:555 dot 0100") == {"tel:555"}
    assert extract_urls("data:text/html,hi dot there") == {"data:text/html,hi"}


def test_a_gap_needs_a_label_on_both_sides() -> None:
    assert extract_urls("http:// dot example") == frozenset()
    assert extract_urls("http://evil dot ") == {"http://evil"}
    assert extract_urls("http://evil dotexample") == {"http://evil"}
    assert extract_urls("http://evildot example") == {"http://evildot"}


def test_only_the_host_is_split_never_the_path() -> None:
    assert extract_urls("http://evil dot example/a b") == {"http://evil.example/a"}
    assert extract_urls("http://evil dot example?q=1") == {"http://evil.example?q=1"}


def test_a_split_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed(f"go to {_SPLIT_HOST} ") == f"go to {REDACTED_LINK} "
    plain = _filter(set(extract_urls(_SPLIT_HOST)))
    assert plain.feed("go to https://evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_a_split_host_leaves_no_host_beside_the_marker() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"Please visit {_SPLIT_HOST} now.") == f"Please visit {REDACTED_LINK} now."


def test_strict_tainted_turn_redacts_a_split_host() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"see {_SPLIT_HOST} ") == f"see {REDACTED_LINK} "


def test_a_split_host_arriving_across_chunks_is_carried_not_lost() -> None:
    for tail in (" ", " d", " do", " dot", " dot ", " [do", " &#4", " %2"):
        guard = _filter({"https://evil.example/pay"})
        assert guard.feed(f"at https://evil{tail}") == "at "
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https://evil dot ") == "at "
    assert guard.feed("example/pay ") == f"{REDACTED_LINK} "


def test_prose_after_a_dotless_host_still_streams_through() -> None:
    guard = _filter({"https://evil.example/pay"})
    assert guard.feed("at https://other now") == "at https://other now"
    assert guard.feed("at https://ok.example/x ") == "at https://ok.example/x "


def test_a_split_host_survives_a_one_character_stream() -> None:
    guard = _filter({"https://evil.example/pay"})
    reply = f"settle at {_SPLIT_HOST} now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_the_split_host_composes_with_earlier_classes() -> None:
    assert extract_urls("hxxps://ev\u200bil &#46; example/pay") == _PLAIN_LINK
    assert extract_urls("hxxps://evil [dot] ex\u3002ample/pay") == {"https://evil.ex.ample/pay"}


def test_a_gap_is_written_with_every_space_nfkc_folds() -> None:
    for space in ("\u00a0", "\u2009", "\u3000", "\u202f"):
        assert extract_urls(f"hxxps://evil{space}dot{space}example/pay") == _PLAIN_LINK
    assert extract_urls("hxxps://evil\u00a0dot\u2009example/pay") == _PLAIN_LINK


def test_the_gap_space_table_is_exactly_what_nfkc_folds_to_a_space() -> None:
    folded = {
        chr(point)
        for point in range(sys.maxunicode + 1)
        if chr(point) not in " \t" and unicodedata.normalize("NFKC", chr(point)) == " "
    }
    assert set(NFKC_SPACES) == folded


def test_whitespace_that_breaks_a_line_is_not_a_gap() -> None:
    for breaker in ("\n", "\r", "\u2028", "\u1680"):
        assert extract_urls(f"http://evil{breaker}dot{breaker}example") == {"http://evil"}


# U+0406 renders as the `l` it replaces. It is one of the 700 UTS-39 characters aimed at an
# ASCII host that the curated confusable table does not contain.
_UNTABLED = "http://examp\u0406e.com/invoice"
_LEGIT = "http://example.com/invoice"

_IDN = "https://bücher.example/pay"

_POLICIES: tuple[OutputGuardrail, ...] = (
    UrlRedactingGuardrail(),
    LookalikeUrlRedactingGuardrail(),
    StrictUrlRedactingGuardrail(),
)
_POLICY_IDS = ("redact", "lookalike", "strict")


def _lookalike(taint: _Taint, allow: frozenset[str] = frozenset()) -> OutputFilter:
    return LookalikeUrlRedactingGuardrail().open(taint, allow=allow)


def test_a_homoglyph_outside_the_curated_table_leaks_under_the_default_and_not_the_lookalike() -> (
    None
):
    tainted = _Taint(tainted=True, untrusted_urls={_LEGIT})
    reply = f"Full report at {_UNTABLED} today."
    default = _filter({_LEGIT})
    assert default.feed(reply) + default.flush() == reply
    guard = _lookalike(tainted)
    assert guard.feed(reply) + guard.flush() == f"Full report at {REDACTED_LINK} today."


def test_the_lookalike_policy_still_redacts_a_verbatim_collected_url() -> None:
    guard = _lookalike(_Taint(tainted=True, untrusted_urls={EVIL}))
    assert guard.feed(f"see {EVIL} now") + guard.flush() == f"see {REDACTED_LINK} now"


def test_the_lookalike_policy_leaves_an_uncollected_ascii_link_alone() -> None:
    guard = _lookalike(_Taint(tainted=True, untrusted_urls={EVIL}))
    text = "the docs live at https://good.example/doc today"
    assert guard.feed(text) + guard.flush() == text


def test_a_host_built_wholly_from_the_curated_table_is_still_read_as_a_lookalike() -> None:
    guard = _lookalike(_Taint(tainted=True))
    assert guard.feed(f"pay at {_CYRILLIC_PACE} ") + guard.flush() == f"pay at {REDACTED_LINK} "
    default = _filter({EVIL})
    assert default.feed(f"pay at {_CYRILLIC_PACE} ") == f"pay at {_CYRILLIC_PACE} "


def test_the_lookalike_ground_needs_no_url_to_have_been_collected() -> None:
    guard = _lookalike(_Taint(tainted=True))
    assert guard.feed(f"try {_UNTABLED} ") + guard.flush() == f"try {REDACTED_LINK} "


def test_an_untainted_turn_is_untouched_by_the_lookalike_policy() -> None:
    guard = _lookalike(_Taint())
    assert guard.feed(f"read {_IDN} now") + guard.flush() == f"read {_IDN} now"


def test_the_measured_cost_is_an_internationalized_domain_on_a_tainted_turn() -> None:
    # A genuine international domain is redacted with the lookalikes, since telling the two apart
    # needs a script database. Measured on the Tranco list: 0 of the top 1,000 hosts, 8 of the top
    # 10,000 and 1,441 of 1,000,000.
    guard = _lookalike(_Taint(tainted=True))
    assert guard.feed(f"buy at {_IDN} ") + guard.flush() == f"buy at {REDACTED_LINK} "


def test_a_lookalike_written_in_punycode_is_redacted_too() -> None:
    guard = _lookalike(_Taint(tainted=True))
    fed = guard.feed("go to https://xn--bcher-kva.example/pay ") + guard.flush()
    assert fed == f"go to {REDACTED_LINK} "


def test_a_non_ascii_path_is_not_a_lookalike() -> None:
    guard = _lookalike(_Taint(tainted=True))
    text = "see https://ru.wikipedia.example/wiki/Привет now"
    assert guard.feed(text) + guard.flush() == text


def test_a_mailto_domain_is_the_host_the_ground_reads() -> None:
    guard = _lookalike(_Taint(tainted=True))
    plain = "write to mailto:abuse@evil.example now"
    assert guard.feed(plain) + guard.flush() == plain
    spoofed = _lookalike(_Taint(tainted=True))
    fed = spoofed.feed("write to mailto:abuse@\u0435vil.example now") + spoofed.flush()
    assert fed == f"write to {REDACTED_LINK} now"


def test_a_scheme_that_names_no_host_is_never_a_lookalike() -> None:
    guard = _lookalike(_Taint(tainted=True))
    text = "call tel:+15550000000 or open data:text/plain,\u0435vil now"
    assert guard.feed(text) + guard.flush() == text


def test_a_user_sent_lookalike_survives_the_lookalike_policy() -> None:
    guard = _lookalike(_Taint(tainted=True), allow=frozenset({_IDN}))
    assert guard.feed(f"as you said, {_IDN} ") + guard.flush() == f"as you said, {_IDN} "


def test_an_opaque_turn_escalates_the_lookalike_policy_to_strict() -> None:
    guard = _lookalike(_Taint(tainted=True, opaque=True))
    fed = guard.feed("the sign reads https://plain.example/pay ") + guard.flush()
    assert fed == f"the sign reads {REDACTED_LINK} "


def test_a_lookalike_split_across_deltas_is_still_redacted() -> None:
    guard = _lookalike(_Taint(tainted=True))
    reply = f"settle at {_UNTABLED} now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_every_policy_leaves_a_clean_turn_byte_identical(policy: OutputGuardrail) -> None:
    guard = policy.open(_Taint(), allow=frozenset())
    text = f"the docs are at {EVIL} and {_IDN} today"
    assert guard.feed(text) + guard.flush() == text


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_every_policy_lets_the_users_own_url_through(policy: OutputGuardrail) -> None:
    guard = policy.open(_Taint(tainted=True, untrusted_urls={EVIL}), allow=frozenset({EVIL}))
    assert guard.feed(f"quoting {EVIL} back") + guard.flush() == f"quoting {EVIL} back"


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_every_policy_distrusts_every_link_on_an_opaque_turn(policy: OutputGuardrail) -> None:
    guard = policy.open(_Taint(tainted=True, opaque=True), allow=frozenset())
    fed = guard.feed("the capture shows https://plain.example/x ") + guard.flush()
    assert fed == f"the capture shows {REDACTED_LINK} "


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_every_policy_ignores_an_opaque_bit_without_taint(policy: OutputGuardrail) -> None:
    guard = policy.open(_Taint(opaque=True), allow=frozenset())
    assert guard.feed(f"see {EVIL} ") + guard.flush() == f"see {EVIL} "


def test_host_of_reads_the_authority_and_drops_what_does_not_decide_the_destination() -> None:
    assert host_of("https://evil.example/pay?q=1#top") == "evil.example"
    assert host_of("https://user:pw@evil.example:8443/pay") == "evil.example:8443"
    assert host_of("https://evil.example") == "evil.example"
    assert host_of("https://[::1]/pay") == "[::1]"


def test_host_of_reads_a_mailto_domain_and_no_other_opaque_scheme() -> None:
    assert host_of("mailto:abuse@evil.example?subject=hi") == "evil.example"
    assert host_of("tel:+15550000000") == ""
    assert host_of("data:text/plain,evil") == ""
    assert host_of("not a url at all") == ""


_TAB_LINK = "https://evil.exa\tmple/pay"


def test_extract_urls_reads_a_tab_a_url_parser_removes() -> None:
    assert extract_urls(_TAB_LINK) == _PLAIN_LINK
    assert extract_urls("https://evil.example/p\tay") == _PLAIN_LINK
    assert extract_urls("https://evil.example\t/pay") == _PLAIN_LINK


def test_a_tab_folds_out_of_every_scheme_the_grammar_reads() -> None:
    assert extract_urls("mailto:me\tyou@evil.example") == {"mailto:meyou@evil.example"}
    assert extract_urls("tel:555\t0100") == {"tel:5550100"}
    assert extract_urls("data:text/html,hi\tthere") == {"data:text/html,hithere"}


def test_a_tab_split_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter(set(_PLAIN_LINK))
    assert guard.feed(f"go to {_TAB_LINK} ") == f"go to {REDACTED_LINK} "
    plain = _filter(set(extract_urls(_TAB_LINK)))
    assert plain.feed("go to https://evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_a_tab_leaves_no_host_beside_the_marker() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed(f"Please visit {_TAB_LINK} now.") == f"Please visit {REDACTED_LINK} now."


def test_a_line_break_is_not_a_removal() -> None:
    # A line break is not treated like a tab: over the repo's own prose it would extend 42
    # matches into the next line, against none for the tab.
    for breaker in ("\n", "\r"):
        assert extract_urls(f"https://evil.exa{breaker}mple/pay") == {"https://evil.exa"}
    assert extract_urls("https://evil.example/pay\nand the next line") == _PLAIN_LINK


def test_a_tab_between_two_labels_is_still_the_gap() -> None:
    assert extract_urls("https://evil\tdot\texample/pay") == _PLAIN_LINK
    assert extract_urls("https://evil \t dot \t example/pay") == _PLAIN_LINK
    assert extract_urls("hxxps://evil dot exa\tmple/pay") == _PLAIN_LINK


def test_the_host_grammar_still_excludes_the_tab() -> None:
    assert extract_urls("https:evil.exa\tmple/pay") == _PLAIN_LINK
    assert extract_urls("https:evil\texample.com/pay") == frozenset()


def test_a_tab_beside_a_link_is_the_accepted_cost() -> None:
    # A tab right after a link is inside the match, so a strict turn redacts the word behind it
    # too. That happens nowhere in the repo's own prose: 0 times over 1,054 files and 1,348,844
    # words.
    assert extract_urls("http://ok.example/x\tand the next word") == {"http://ok.example/xand"}
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("see http://ok.example/x\tand the rest.") == f"see {REDACTED_LINK} the rest."
    assert _strict(_Taint(tainted=True)).feed("a tab\there") == "a tab\there"


def test_a_tab_carrying_url_arriving_across_chunks_is_carried_not_lost() -> None:
    guard = _filter(set(_PLAIN_LINK))
    assert guard.feed("at https://evil.exa\t") == "at "
    assert guard.feed("mple/pay ") == f"{REDACTED_LINK} "


def test_a_tab_carrying_url_survives_a_one_character_stream() -> None:
    guard = _filter(set(_PLAIN_LINK))
    reply = f"settle at {_TAB_LINK} now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_the_tab_removal_composes_with_earlier_classes() -> None:
    assert extract_urls("https&#58;//evil.exa\tmple/pay") == _PLAIN_LINK
    assert extract_urls("https://ev\u200bil.exa\tmple/pay") == _PLAIN_LINK
    assert extract_urls("hxxps://evil[.]exa\tmple/pay") == _PLAIN_LINK
    assert extract_urls("https:\\\\evil.exa\tmple/pay") == _PLAIN_LINK


def test_extract_urls_anchors_a_slashless_authority_whose_host_is_split() -> None:
    assert extract_urls("https:evil dot example/pay") == _PLAIN_LINK
    assert extract_urls("hxxps:evil dot example/pay") == _PLAIN_LINK
    assert extract_urls("https:/evil dot example/pay") == _PLAIN_LINK
    assert extract_urls("http[:]evil dot example/pay") == {"http://evil.example/pay"}
    assert extract_urls("https:a dot b dot example") == {"https://a.b.example"}


def test_the_split_anchor_inherits_the_gap_tables_rather_than_growing_one() -> None:
    for form in ("dot", ".", "。", "&#46;", "%2e", "[dot]"):
        assert extract_urls(f"https:evil {form} example/pay") == _PLAIN_LINK
    assert extract_urls("https:evil\u00a0dot\u2009example/pay") == _PLAIN_LINK


def test_the_split_anchor_still_declines_the_prose_the_slashless_form_protects() -> None:
    assert extract_urls("https:no slashes here") == frozenset()
    assert extract_urls("the https: scheme is named that way") == frozenset()
    assert extract_urls("https:scheme") == frozenset()
    assert extract_urls("http:foo") == frozenset()
    assert extract_urls("https:localhost and https:evil./pay") == frozenset()
    assert extract_urls("https: evil dot example") == frozenset()


def test_a_dotted_host_is_still_finished_before_any_gap_at_the_slashless_position_too() -> None:
    assert extract_urls("visit https:example.com dot the file is there") == {"https://example.com"}


def test_only_an_authority_scheme_reaches_the_split_anchor() -> None:
    assert extract_urls("mailto:evil dot example") == {"mailto:evil"}
    assert extract_urls("tel:evil dot example") == {"tel:evil"}
    assert extract_urls("data:evil dot example") == frozenset()


def test_a_slashless_split_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter(set(_PLAIN_LINK))
    assert guard.feed("go to https:evil dot example/pay ") == f"go to {REDACTED_LINK} "
    plain = _filter(set(extract_urls("https:evil dot example/pay")))
    assert plain.feed("go to https://evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_strict_tainted_turn_redacts_a_slashless_split_host() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("Please visit https:evil dot example/pay now.") == (
        f"Please visit {REDACTED_LINK} now."
    )


def test_a_slashless_split_host_arriving_across_chunks_is_carried_not_lost() -> None:
    guard = _filter(set(_PLAIN_LINK))
    assert guard.feed("at https:evil ") == "at "
    assert guard.feed("dot example/pay ") == f"{REDACTED_LINK} "


def test_a_slashless_split_host_survives_a_one_character_stream() -> None:
    guard = _filter(set(_PLAIN_LINK))
    reply = "settle at https:evil dot example/pay now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_carrying_a_slashless_opening_is_not_redacting_it() -> None:
    guard = _strict(_Taint(tainted=True))
    reply = "the https:no slashes here at all"
    assert "".join(guard.feed(char) for char in reply) + guard.flush() == reply


def test_the_split_slashless_host_composes_with_earlier_classes() -> None:
    assert extract_urls("hxxps&#58;ev\u200bil [dot] example/pay") == _PLAIN_LINK
    assert extract_urls("https：evil 。 example/pay") == _PLAIN_LINK  # noqa: RUF001


def test_normalizing_without_the_confusable_fold_leaves_the_letters_written() -> None:
    assert normalize_url("hxxp://\u0420ACE.example") == "http://pace.example"
    assert (
        normalize_url("hxxp://\u0420ACE.example", confusables=False) == "http://\u0440ace.example"
    )


def test_extract_urls_reads_a_tab_inside_a_scheme_word() -> None:
    assert extract_urls("ht\ttp://evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("htt\tps://evil.example/pay") == _PLAIN_LINK
    assert extract_urls("h\tttps://evil.example/pay") == _PLAIN_LINK
    assert extract_urls("mail\tto:me@evil.example") == {"mailto:me@evil.example"}
    assert extract_urls("te\tl:5550100") == {"tel:5550100"}
    assert extract_urls("da\tta:text/plain,x") == {"data:text/plain,x"}


def test_a_tab_stands_inside_a_defanged_scheme_word_at_every_position() -> None:
    assert extract_urls("hxx\tp://evil.example/pay") == {"http://evil.example/pay"}
    assert extract_urls("h\txxps://evil.example/pay") == _PLAIN_LINK
    assert extract_urls("hx\txps://evil.example/pay") == _PLAIN_LINK


def test_a_tab_stands_inside_the_separator_too() -> None:
    for form in (
        "https\t://evil.example/pay",
        "https:\t//evil.example/pay",
        "https:/\t/evil.example/pay",
        "https[:\t//]evil.example/pay",
        "https\t[://]evil.example/pay",
        "https\t:evil.example/pay",
        "https\t&#58;//evil.example/pay",
    ):
        assert extract_urls(form) == _PLAIN_LINK


def test_a_tab_inside_a_defang_token_no_longer_truncates_the_host() -> None:
    assert extract_urls("https://evil[d\tot]example/pay") == _PLAIN_LINK
    assert extract_urls("https://evil[\t.]example/pay") == _PLAIN_LINK
    assert extract_urls("https://evil[.\t]example/pay") == _PLAIN_LINK


def test_a_tab_does_not_reach_inside_an_entity_reference() -> None:
    assert extract_urls("https&#5\t8;//evil.example/pay") == frozenset()
    assert extract_urls("https&col\ton;//evil.example/pay") == frozenset()


def test_a_tab_inside_a_gap_token_is_still_the_gap() -> None:
    assert extract_urls("https://evil d\tot example/pay") == _PLAIN_LINK
    assert extract_urls("https://evil [d\tot] example/pay") == _PLAIN_LINK


def test_a_tab_carrying_scheme_transform_of_a_collected_url_is_redacted() -> None:
    guard = _filter(set(_PLAIN_LINK))
    assert guard.feed("go to htt\tps://evil.example/pay ") == f"go to {REDACTED_LINK} "
    plain = _filter(set(extract_urls("htt\tps://evil.example/pay")))
    assert plain.feed("go to https://evil.example/pay ") == f"go to {REDACTED_LINK} "


def test_strict_tainted_turn_redacts_a_tab_carrying_scheme() -> None:
    guard = _strict(_Taint(tainted=True))
    assert guard.feed("Please visit ht\ttps://evil.example/pay now.") == (
        f"Please visit {REDACTED_LINK} now."
    )


def test_a_tab_split_scheme_arriving_across_chunks_is_carried_not_lost() -> None:
    guard = _filter(set(_PLAIN_LINK))
    assert guard.feed("at ht\tt") == "at "
    assert guard.feed("ps://evil.example/pay ") == f"{REDACTED_LINK} "


def test_a_tab_carrying_scheme_survives_a_one_character_stream() -> None:
    guard = _filter(set(_PLAIN_LINK))
    reply = "settle at ht\ttps://evil.example/pay now"
    fed = "".join(guard.feed(char) for char in reply) + guard.flush()
    assert fed == f"settle at {REDACTED_LINK} now"


def test_the_removal_inside_a_word_composes_with_earlier_classes() -> None:
    assert extract_urls("hx\txps&#58;//evil.example/pay") == _PLAIN_LINK
    assert extract_urls("hxx\tps://ev\u200bil d\tot example/pay") == _PLAIN_LINK
    assert extract_urls("ht\ttps:evil dot example/pay") == _PLAIN_LINK


def _removed(guard: OutputFilter, reply: str) -> dict[str, int]:
    guard.feed(reply)
    guard.flush()
    return dict(guard.redactions())


def test_each_policy_opens_a_filter_under_its_configured_name() -> None:
    assert [policy.open(_Taint(), allow=frozenset()).policy for policy in _POLICIES] == [
        "redact",
        "lookalike",
        "strict",
    ]


def test_a_filter_that_replaced_nothing_counts_zero_under_every_ground() -> None:
    for policy in _POLICIES:
        guard = policy.open(_Taint(tainted=True), allow=frozenset({EVIL}))
        assert _removed(guard, f"see {EVIL} ") == {"collected": 0, "lookalike": 0, "link": 0}


def test_the_lookalike_ground_counts_only_what_no_other_ground_removed() -> None:
    collected_idn = "https://bücher.example/collected"
    taint = _Taint(tainted=True, untrusted_urls={collected_idn})
    reply = f"a {collected_idn} b {_IDN} c {_UNTABLED} d {_LEGIT} e"
    guard = _lookalike(taint, allow=frozenset({normalize_url(_UNTABLED)}))
    assert _removed(guard, reply) == {"collected": 1, "lookalike": 1, "link": 0}


def test_the_link_ground_counts_on_a_strict_or_opaque_turn() -> None:
    strict = _strict(_Taint(tainted=True, untrusted_urls={EVIL}))
    assert _removed(strict, f"{EVIL} and {_IDN} ") == {"collected": 0, "lookalike": 0, "link": 2}
    opaque = _lookalike(_Taint(tainted=True, opaque=True, untrusted_urls={EVIL}))
    counts = _removed(opaque, f"{EVIL} and {_IDN} and {_LEGIT} ")
    assert counts == {"collected": 1, "lookalike": 0, "link": 2}


def test_counts_accumulate_across_feeds_and_the_flush() -> None:
    guard = _filter({EVIL})
    guard.feed(f"{EVIL} then ")
    guard.feed(f"{EVIL} then https://evil.exa")
    assert guard.redactions()["collected"] == 2
    guard.feed("mple/report")
    guard.flush()
    assert guard.redactions() == {"collected": 3, "lookalike": 0, "link": 0}
